import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from bson import ObjectId
from fastapi import HTTPException
from starlette.requests import Request

from app.core.access_control import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import Role


USER_ID = str(ObjectId())


def request_with_cookie(token=None):
    headers = []

    if token is not None:
        headers.append((
            b"cookie",
            f"fleetpulse_access_token={token}".encode("ascii"),
        ))

    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/v1/accounts/me",
        "headers": headers,
    })


def fake_user(
    role=Role.CUSTOMER,
    active=True,
    version=0,
):
    return SimpleNamespace(
        id=ObjectId(USER_ID),
        role=role,
        is_active=active,
        auth_version=version,
    )


def assert_rejected(
    token=None,
    user=None,
    should_query=False,
):
    with patch(
        "app.core.access_control.User.get",
        new_callable=AsyncMock,
        return_value=user,
    ) as mocked_get:

        with pytest.raises(HTTPException) as error:
            asyncio.run(
                get_current_user(
                    request_with_cookie(token)
                )
            )

        assert error.value.status_code == 401

        if not should_query:
            mocked_get.assert_not_awaited()


@pytest.mark.parametrize("role", list(Role))
def test_all_existing_roles_can_verify_own_session(role):
    token = create_access_token(
        USER_ID,
        auth_version=2,
    )

    user = fake_user(role=role, version=2)

    with patch(
        "app.core.access_control.User.get",
        new_callable=AsyncMock,
        return_value=user,
    ) as mocked_get:

        result = asyncio.run(
            get_current_user(request_with_cookie(token))
        )

        assert result is user

        mocked_get.assert_awaited_once_with(
            ObjectId(USER_ID)
        )


def test_missing_cookie_rejected():
    assert_rejected()


def test_invalid_token_rejected():
    assert_rejected(token="not.a.valid.jwt")


def test_tampered_signature_rejected():
    token = create_access_token(USER_ID)

    header, payload, signature = token.split(".")

    first = "A" if signature[0] != "A" else "B"

    tampered = (
        f"{header}.{payload}.{first}{signature[1:]}"
    )

    assert_rejected(token=tampered)


def test_invalid_mongodb_user_id_rejected():
    assert_rejected(
        token=create_access_token("not-an-object-id")
    )


def test_deleted_user_rejected():
    assert_rejected(
        token=create_access_token(USER_ID),
        user=None,
        should_query=True,
    )


def test_disabled_user_rejected():
    assert_rejected(
        token=create_access_token(USER_ID),
        user=fake_user(active=False),
        should_query=True,
    )


def test_auth_version_mismatch_rejected():
    assert_rejected(
        token=create_access_token(
            USER_ID,
            auth_version=0,
        ),
        user=fake_user(version=1),
        should_query=True,
    )


def test_password_reset_invalidates_old_session():
    user = fake_user(version=0)

    old_token = create_access_token(
        USER_ID,
        auth_version=0,
    )

    with patch(
        "app.core.access_control.User.get",
        new_callable=AsyncMock,
        return_value=user,
    ):
        assert asyncio.run(
            get_current_user(request_with_cookie(old_token))
        ) is user

        # Simulates the reset service incrementing auth_version.
        user.auth_version += 1

        with pytest.raises(HTTPException) as error:
            asyncio.run(
                get_current_user(request_with_cookie(old_token))
            )

        assert error.value.status_code == 401

        fresh_token = create_access_token(
            USER_ID,
            auth_version=1,
        )

        assert asyncio.run(
            get_current_user(request_with_cookie(fresh_token))
        ) is user


def test_expired_session_rejected():
    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": USER_ID,
            "type": "access",
            "ver": 0,
            "iat": now - timedelta(hours=1),
            "exp": now - timedelta(minutes=1),
        },
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )

    assert_rejected(token=token)


def test_role_based_endpoint_authorization():
    from types import SimpleNamespace

    from fastapi import Depends, FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.core.access_control import (
        get_current_user,
        require_roles,
    )

    async def run_tests():
        app = FastAPI()

        @app.get("/test/admin")
        async def admin_only(
            user=Depends(require_roles(Role.ADMIN)),
        ):
            return {"role": user.role.value}

        @app.get("/test/dispatch")
        async def dispatch_access(
            user=Depends(
                require_roles(
                    Role.ADMIN,
                    Role.DISPATCHER,
                )
            ),
        ):
            return {"role": user.role.value}

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            # Admin permissions
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(role=Role.ADMIN)
            )

            assert (
                await client.get("/test/admin")
            ).status_code == 200

            assert (
                await client.get("/test/dispatch")
            ).status_code == 200

            print("Admin permissions: PASSED")

            # Dispatcher permissions
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(role=Role.DISPATCHER)
            )

            assert (
                await client.get("/test/admin")
            ).status_code == 403

            assert (
                await client.get("/test/dispatch")
            ).status_code == 200

            print("Dispatcher permissions: PASSED")

            # Driver permissions
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(role=Role.DRIVER)
            )

            assert (
                await client.get("/test/admin")
            ).status_code == 403

            assert (
                await client.get("/test/dispatch")
            ).status_code == 403

            print("Driver restrictions: PASSED")

            # Customer permissions
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(role=Role.CUSTOMER)
            )

            assert (
                await client.get("/test/admin")
            ).status_code == 403

            assert (
                await client.get("/test/dispatch")
            ).status_code == 403

            print("Customer restrictions: PASSED")

            # Unauthenticated access
            app.dependency_overrides.clear()

            assert (
                await client.get("/test/admin")
            ).status_code == 401

            print("Unauthenticated rejection: PASSED")

        print("RBAC AUTOMATED TEST PASSED")

    asyncio.run(run_tests())


def test_require_roles_rejects_empty_permissions():
    from app.core.access_control import require_roles

    with pytest.raises(ValueError):
        require_roles()

    print("Empty role configuration rejection: PASSED")
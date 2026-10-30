import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

from app.core.security import (
    create_access_token,
    create_csrf_token,
)

from app.controllers.accounts.login_controller import (
    router as login_router,
)

from app.controllers.accounts.logout_controller import (
    router as logout_router,
)


USER_ID = "507f1f77bcf86cd799439011"


def test_logout_api_contract():

    async def run_tests():
        app = FastAPI()

        app.include_router(
            login_router,
            prefix="/api/v1",
        )

        app.include_router(
            logout_router,
            prefix="/api/v1",
        )

        @app.post("/api/v1/_test_login")
        async def simulate_login(response: Response):
            response.set_cookie(
                key="fleetpulse_access_token",
                value=create_access_token(USER_ID, 0),
                httponly=True,
                secure=False,
                samesite="lax",
                path="/api/v1",
            )

            return {"message": "Test session created"}

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            # Unauthenticated users cannot obtain CSRF tokens.
            unauthorized = await client.get(
                "/api/v1/accounts/csrf"
            )

            assert unauthorized.status_code == 401
            print("Unauthenticated CSRF request: PASSED")

            fake_user = SimpleNamespace(
                is_active=True,
                auth_version=0,
            )

            with patch(
                "app.core.access_control.User.get",
                new_callable=AsyncMock,
                return_value=fake_user,
            ):

                login = await client.post(
                    "/api/v1/_test_login"
                )

                assert login.status_code == 200
                print("Test session creation: PASSED")

                # Obtain valid CSRF token.
                csrf_response = await client.get(
                    "/api/v1/accounts/csrf"
                )

                assert csrf_response.status_code == 200

                csrf_token = csrf_response.json()[
                    "csrf_token"
                ]

                assert csrf_token
                assert csrf_response.headers[
                    "cache-control"
                ] == "no-store"

                print("CSRF token endpoint: PASSED")

                # Missing CSRF token.
                missing = await client.post(
                    "/api/v1/accounts/logout"
                )

                assert missing.status_code == 403

                print("Missing CSRF rejection: PASSED")

                # Invalid CSRF token.
                invalid = await client.post(
                    "/api/v1/accounts/logout",
                    headers={
                        "X-CSRF-Token": "invalid-token"
                    },
                )

                assert invalid.status_code == 403

                print("Invalid CSRF rejection: PASSED")

                # Token from a different session.
                different_session = create_access_token(
                    USER_ID,
                    1,
                )

                other_csrf = create_csrf_token(
                    different_session
                )

                mismatched = await client.post(
                    "/api/v1/accounts/logout",
                    headers={
                        "X-CSRF-Token": other_csrf
                    },
                )

                assert mismatched.status_code == 403

                print("Session binding: PASSED")

                # Valid logout.
                result = await client.post(
                    "/api/v1/accounts/logout",
                    headers={
                        "X-CSRF-Token": csrf_token
                    },
                )

                assert result.status_code == 200

                assert result.json()["message"] == (
                    "Logged out successfully"
                )

                print("Valid logout: PASSED")

                # Cookie must be cleared.
                cookie = result.headers[
                    "set-cookie"
                ].lower()

                assert "fleetpulse_access_token=" in cookie
                assert "max-age=0" in cookie
                assert "path=/api/v1" in cookie
                assert "httponly" in cookie

                print("Cookie removal: PASSED")

                after = await client.get(
                    "/api/v1/accounts/csrf"
                )

                assert after.status_code == 401

                print("Session terminated: PASSED")

        print("CSRF LOGOUT AUTOMATED TEST PASSED")

    asyncio.run(run_tests())
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    decode_access_token_claims,
    hash_password,
    verify_password,
)
from app.models.user import Role, User
from app.schemas.accounts.register_schemas import RegisterRequest
from app.services.accounts import password_reset_service as reset_service


USER_ID = "507f1f77bcf86cd799439011"


class FakeField:
    def __eq__(self, value):
        return ("equals", value)

    def __gt__(self, value):
        return ("greater_than", value)


class FakeQuery:
    def __init__(self, found=None, matched_count=1):
        self.found = found
        self.matched_count = matched_count
        self.update_document = None

    def __await__(self):
        async def get_result():
            return self.found

        return get_result().__await__()

    async def update(self, document):
        self.update_document = document
        return SimpleNamespace(matched_count=self.matched_count)


class FakeUser:
    email = FakeField()
    reset_token_hash = FakeField()
    reset_token_expires_at = FakeField()
    is_active = FakeField()
    query = None

    @classmethod
    def find_one(cls, *conditions):
        return cls.query


def test_user_model_security_defaults():
    fields = User.model_fields

    assert fields["role"].default == Role.CUSTOMER
    assert fields["is_active"].default is True
    assert fields["reset_token_hash"].default is None
    assert fields["reset_token_expires_at"].default is None
    assert fields["auth_version"].default == 0

    index = User.Settings.indexes[0].document
    assert index["unique"] is True
    assert dict(index["key"]) == {"email": 1}


def test_public_registration_rejects_privileged_role():
    with pytest.raises(ValidationError):
        RegisterRequest(
            full_name="Test Customer",
            email="test@example.com",
            password="Password123!",
            role="admin",
        )


def test_password_hashing_and_verification():
    original = "FleetPulse@Test123"
    stored = hash_password(original)

    assert stored != original
    assert stored.startswith("$2")
    assert verify_password(original, stored)
    assert not verify_password("WrongPassword", stored)
    assert not verify_password(original, "invalid-hash")


def test_bcrypt_rejects_over_72_utf8_bytes():
    with pytest.raises(ValueError):
        hash_password("🔒" * 19)

    assert not verify_password("🔒" * 19, "invalid-hash")


def test_access_token_claims_and_version():
    token = create_access_token(USER_ID, auth_version=3)

    assert decode_access_token_claims(token) == (USER_ID, 3)
    assert decode_access_token(token) == USER_ID


@pytest.mark.parametrize("bad_version", [-1, True, "1", None])
def test_reject_invalid_auth_version_on_creation(bad_version):
    with pytest.raises(ValueError):
        create_access_token(USER_ID, auth_version=bad_version)


def test_reject_token_without_auth_version():
    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": USER_ID,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token_claims(token)


def test_reject_expired_token():
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

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token_claims(token)


def test_reject_wrong_token_type():
    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": USER_ID,
            "type": "reset",
            "ver": 0,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token_claims(token)


def test_reset_token_is_random_and_hashed():
    one = reset_service.generate_reset_token()
    two = reset_service.generate_reset_token()

    assert one != two
    assert len(one) >= 32

    hashed = reset_service.hash_reset_token(one)

    assert len(hashed) == 64
    assert hashed != one
    assert hashed == reset_service.hash_reset_token(one)


def test_reset_request_stores_hash_and_expiry_only():
    async def run():
        account = SimpleNamespace(
            is_active=True,
            reset_token_hash=None,
            reset_token_expires_at=None,
            save=AsyncMock(),
        )

        FakeUser.query = FakeQuery(found=account)

        with patch.object(reset_service, "User", FakeUser):
            token = await reset_service.request_password_reset(
                "TEST@example.com"
            )

        assert token is not None
        assert account.reset_token_hash == reset_service.hash_reset_token(token)
        assert account.reset_token_hash != token

        remaining = (
            account.reset_token_expires_at
            - datetime.now(timezone.utc)
        )

        assert timedelta(minutes=14) < remaining <= timedelta(minutes=15)
        account.save.assert_awaited_once()

    asyncio.run(run())


def test_unknown_account_does_not_issue_reset_token():
    async def run():
        FakeUser.query = FakeQuery(found=None)

        with patch.object(reset_service, "User", FakeUser):
            assert (
                await reset_service.request_password_reset(
                    "unknown@example.com"
                )
                is None
            )

    asyncio.run(run())


def test_reset_consumes_token_and_increments_auth_version():
    async def run():
        FakeUser.query = FakeQuery(matched_count=1)

        with patch.object(reset_service, "User", FakeUser):
            await reset_service.reset_password(
                "a" * 43,
                "NewPassword123!",
            )

        updates = FakeUser.query.update_document

        assert updates["$set"]["reset_token_hash"] is None
        assert updates["$set"]["reset_token_expires_at"] is None
        assert updates["$inc"]["auth_version"] == 1

        assert verify_password(
            "NewPassword123!",
            updates["$set"]["password_hash"],
        )

    asyncio.run(run())


def test_reset_rejects_consumed_or_expired_token():
    async def run():
        FakeUser.query = FakeQuery(matched_count=0)

        with patch.object(reset_service, "User", FakeUser):
            with pytest.raises(reset_service.InvalidResetTokenError):
                await reset_service.reset_password(
                    "b" * 43,
                    "NewPassword123!",
                )

    asyncio.run(run())
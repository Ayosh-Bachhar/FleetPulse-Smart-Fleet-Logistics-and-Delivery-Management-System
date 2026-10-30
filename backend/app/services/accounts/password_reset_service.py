import hashlib
import secrets

from datetime import datetime, timedelta, timezone

from app.models.user import User
from app.core.security import hash_password


RESET_TOKEN_EXPIRE_MINUTES = 15


class InvalidResetTokenError(Exception):
    pass


# Generate a secure reset token
def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


# Hash the token before database storage
def hash_reset_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# Request a password reset
async def request_password_reset(
    email: str,
) -> str | None:

    normalized_email = email.strip().lower()

    user = await User.find_one(
        User.email == normalized_email
    )

    if user is None or not user.is_active:
        return None

    reset_token = generate_reset_token()

    user.reset_token_hash = hash_reset_token(
        reset_token
    )

    user.reset_token_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    )

    await user.save()

    # Internal use only: deliver through a secure channel.
    # Never include this token in a public API response.
    return reset_token


# Validate token and update password
async def reset_password(
    token: str,
    new_password: str,
) -> None:

    if not isinstance(token, str) or not (
        32 <= len(token) <= 256
    ):
        raise InvalidResetTokenError(
            "Invalid or expired reset token."
        )

    if len(new_password) < 8:
        raise ValueError(
            "Password must contain at least 8 characters."
        )

    token_hash = hash_reset_token(token)
    now = datetime.now(timezone.utc)

    new_password_hash = hash_password(
        new_password
    )

    # Atomic update prevents a token from being
    # successfully consumed twice.
    result = await User.find_one(
        User.reset_token_hash == token_hash,
        User.reset_token_expires_at > now,
        User.is_active == True,
    ).update(
        {
            "$set": {
                "password_hash": new_password_hash,
                "reset_token_hash": None,
                "reset_token_expires_at": None,
            },
            "$inc": {
                "auth_version": 1,
            },
        }
    )

    if result is None or result.matched_count != 1:
        raise InvalidResetTokenError(
            "Invalid or expired reset token."
        )
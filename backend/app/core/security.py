from datetime import datetime, timedelta, timezone

import hashlib
import hmac
import secrets
import bcrypt
import jwt

from app.core.config import settings


JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# PASSWORD HASHING
def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes.")

    salt = bcrypt.gensalt(rounds=12)

    hashed_password = bcrypt.hashpw(
        password_bytes,
        salt,
    )

    return hashed_password.decode("utf-8")


# PASSWORD VERIFICATION
def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        return False

    try:
        return bcrypt.checkpw(
            password_bytes,
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False



# JWT TOKEN CREATION
def create_access_token(
    user_id: str,
    auth_version: int = 0,
) -> str:
    if not user_id:
        raise ValueError("User ID is required.")

    if (
        isinstance(auth_version, bool)
        or not isinstance(auth_version, int)
        or auth_version < 0
    ):
        raise ValueError("Invalid authentication version.")

    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "type": "access",
        "ver": auth_version,
        "iat": now,
        "exp": now + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


# JWT TOKEN CLAIMS VERIFICATION
def decode_access_token_claims(
    token: str,
) -> tuple[str, int]:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={
            "require": [
                "sub",
                "type",
                "ver",
                "iat",
                "exp",
            ]
        },
    )

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError(
            "Invalid token type."
        )

    user_id = payload.get("sub")
    auth_version = payload.get("ver")

    if not isinstance(user_id, str) or not user_id:
        raise jwt.InvalidTokenError(
            "Invalid user ID."
        )

    if (
        isinstance(auth_version, bool)
        or not isinstance(auth_version, int)
        or auth_version < 0
    ):
        raise jwt.InvalidTokenError(
            "Invalid authentication version."
        )

    return user_id, auth_version


# COMPATIBILITY WITH EXISTING TOKEN TESTS
def decode_access_token(token: str) -> str:
    user_id, _ = decode_access_token_claims(token)
    return user_id


# CSRF TOKEN SECURITY

def create_csrf_token(access_token: str) -> str:
    if not access_token:
        raise ValueError("Access token is required.")

    nonce = secrets.token_hex(16)

    signing_key = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        b"fleetpulse-csrf-v1",
        hashlib.sha256,
    ).digest()

    message = (
        f"{len(access_token)}:{access_token}:{nonce}"
    ).encode("utf-8")

    signature = hmac.new(
        signing_key,
        message,
        hashlib.sha256,
    ).hexdigest()

    return f"{nonce}.{signature}"


def verify_csrf_token(
    access_token: str | None,
    csrf_token: str | None,
) -> bool:
    if not access_token or not csrf_token:
        return False

    parts = csrf_token.split(".")

    if len(parts) != 2:
        return False

    nonce, signature = parts

    if len(nonce) != 32 or len(signature) != 64:
        return False

    try:
        int(nonce, 16)
        int(signature, 16)
    except ValueError:
        return False

    signing_key = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        b"fleetpulse-csrf-v1",
        hashlib.sha256,
    ).digest()

    message = (
        f"{len(access_token)}:{access_token}:{nonce}"
    ).encode("utf-8")

    expected_signature = hmac.new(
        signing_key,
        message,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        signature,
        expected_signature,
    )
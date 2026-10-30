import jwt

from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status

from app.core.security import decode_access_token_claims
from app.models.user import User, Role
from app.core.security import verify_csrf_token


def unauthorized():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required or session expired.",
    )


async def get_current_user(request: Request) -> User:
    token = request.cookies.get(
        "fleetpulse_access_token"
    )

    if not token:
        raise unauthorized()

    try:
        user_id, token_version = decode_access_token_claims(
            token
        )
    except jwt.InvalidTokenError:
        raise unauthorized() from None

    if not ObjectId.is_valid(user_id):
        raise unauthorized()

    user = await User.get(ObjectId(user_id))

    if user is None or not user.is_active:
        raise unauthorized()

    if user.auth_version != token_version:
        raise unauthorized()

    return user


def require_roles(*allowed_roles: Role):
    """
    Restrict API access to the specified roles.
    """

    if not allowed_roles:
        raise ValueError(
            "At least one allowed role is required."
        )

    async def role_guard(
        current_user: User = Depends(get_current_user),
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return current_user

    return role_guard


async def require_csrf(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    access_token = request.cookies.get(
        "fleetpulse_access_token"
    )

    csrf_token = request.headers.get(
        "X-CSRF-Token"
    )

    if not verify_csrf_token(
        access_token,
        csrf_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed.",
        )

    return current_user
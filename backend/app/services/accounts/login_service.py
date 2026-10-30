from app.models.user import User
from app.core.security import (
    verify_password,
    create_access_token,
)
from app.schemas.accounts.login_schemas import (
    LoginRequest,
    LoginResponse,
)


class InvalidCredentialsError(Exception):
    pass


async def login_user(
    data: LoginRequest,
) -> tuple[LoginResponse, str]:

    email = str(data.email).strip().lower()

    user = await User.find_one(
        User.email == email
    )

    if user is None:
        raise InvalidCredentialsError(
            "Invalid email or password."
        )

    if not verify_password(
        data.password,
        user.password_hash,
    ):
        raise InvalidCredentialsError(
            "Invalid email or password."
        )

    if not user.is_active:
        raise InvalidCredentialsError(
            "Invalid email or password."
        )

    access_token = create_access_token(
        str(user.id),
        user.auth_version,
    )

    response = LoginResponse(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        role=user.role,
    )

    return response, access_token
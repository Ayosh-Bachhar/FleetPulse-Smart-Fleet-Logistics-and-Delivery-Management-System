from pymongo.errors import DuplicateKeyError

from app.models.user import User, Role
from app.core.security import hash_password
from app.schemas.accounts.register_schemas import (
    RegisterRequest,
    RegisterResponse,
)


class EmailAlreadyRegisteredError(Exception):
    pass


async def register_user(
    data: RegisterRequest,
) -> RegisterResponse:

    email = str(data.email).strip().lower()

    existing_user = await User.find_one(
        User.email == email
    )

    if existing_user:
        raise EmailAlreadyRegisteredError(
            "An account with this email already exists."
        )

    new_user = User(
        full_name=data.full_name,
        email=email,
        password_hash=hash_password(data.password),
        role=Role.CUSTOMER,
        is_active=True,
    )

    try:
        await new_user.insert()
    except DuplicateKeyError as exc:
        raise EmailAlreadyRegisteredError(
            "An account with this email already exists."
        ) from exc

    return RegisterResponse(
        id=str(new_user.id),
        full_name=new_user.full_name,
        email=new_user.email,
        role=new_user.role,
        created_at=new_user.created_at,
    )
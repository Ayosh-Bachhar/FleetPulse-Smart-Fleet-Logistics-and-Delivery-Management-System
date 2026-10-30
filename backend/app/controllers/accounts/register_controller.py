from fastapi import APIRouter, HTTPException, status

from app.schemas.accounts.register_schemas import (
    RegisterRequest,
    RegisterResponse,
)
from app.services.accounts.register_service import (
    register_user,
    EmailAlreadyRegisteredError,
)


router = APIRouter(
    prefix="/accounts",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterRequest,
):
    try:
        return await register_user(data)

    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
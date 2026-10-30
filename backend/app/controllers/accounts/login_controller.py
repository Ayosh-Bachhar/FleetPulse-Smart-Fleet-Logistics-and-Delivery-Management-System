from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from app.core.security import create_csrf_token
from app.core.access_control import get_current_user
from app.core.security import ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import User
from app.core.config import settings
from app.schemas.accounts.login_schemas import (
    LoginRequest,
    LoginResponse,
)
from app.services.accounts.login_service import (
    login_user,
    InvalidCredentialsError,
)


router = APIRouter(
    prefix="/accounts",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    data: LoginRequest,
    response: Response,
):
    try:
        user_response, access_token = await login_user(data)

    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc

    response.set_cookie(
        key="fleetpulse_access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/api/v1",
    )

    response.headers["Cache-Control"] = "no-store"

    return user_response


@router.get(
    "/me",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return LoginResponse(
        message="Session active",
        id=str(current_user.id),
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
    )


@router.get(
    "/csrf",
    status_code=status.HTTP_200_OK,
)
async def get_csrf_token(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
):
    access_token = request.cookies.get(
        "fleetpulse_access_token"
    )

    csrf_token = create_csrf_token(
        access_token
    )

    response.headers["Cache-Control"] = "no-store"

    return {
        "csrf_token": csrf_token
    }
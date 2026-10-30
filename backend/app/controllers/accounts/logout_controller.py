from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)

from app.core.access_control import require_csrf

from app.schemas.accounts.logout_schemas import (
    LogoutResponse,
)

from app.services.accounts.logout_service import (
    clear_auth_cookie,
)


router = APIRouter(
    prefix="/accounts",
    tags=["Authentication"],
)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
)
async def logout(response: Response):
    clear_auth_cookie(response)

    return LogoutResponse()
import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Response,
    status,
)

from app.schemas.accounts.password_reset_schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)

from app.services.accounts.password_reset_service import (
    request_password_reset,
    reset_password,
    InvalidResetTokenError,
)

from app.integrations.email_client import (
    send_password_reset_email,
    smtp_is_configured,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/accounts",
    tags=["Authentication"],
)


def deliver_reset_email(
    email: str,
    token: str,
) -> None:
    try:
        send_password_reset_email(email, token)
    except Exception:
        logger.exception(
            "Password reset email delivery failed."
        )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def forgot_password(
    data: ForgotPasswordRequest,
    response: Response,
    background_tasks: BackgroundTasks,
):
    response.headers["Cache-Control"] = "no-store"

    if not smtp_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset service is unavailable.",
        )

    reset_token = await request_password_reset(
        str(data.email)
    )

    if reset_token is not None:
        background_tasks.add_task(
            deliver_reset_email,
            str(data.email),
            reset_token,
        )

    return ForgotPasswordResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def change_password(
    data: ResetPasswordRequest,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"

    try:
        await reset_password(
            token=data.token,
            new_password=data.new_password,
        )

    except InvalidResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        ) from exc

    return ResetPasswordResponse()
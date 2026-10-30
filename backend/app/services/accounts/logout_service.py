from fastapi import Response

from app.core.config import settings


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key="fleetpulse_access_token",
        path="/api/v1",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )

    response.headers["Cache-Control"] = "no-store"
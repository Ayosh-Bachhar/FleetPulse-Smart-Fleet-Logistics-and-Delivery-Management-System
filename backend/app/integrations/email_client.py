import smtplib
import ssl

from email.message import EmailMessage
from urllib.parse import quote

from app.core.config import settings


def smtp_is_configured() -> bool:
    return all([
        settings.SMTP_HOST,
        settings.SMTP_USERNAME,
        settings.SMTP_PASSWORD,
        settings.SMTP_FROM_EMAIL,
    ])


def send_password_reset_email(
    recipient_email: str,
    reset_token: str,
) -> None:

    if not smtp_is_configured():
        raise RuntimeError(
            "SMTP email delivery is not configured."
        )

    reset_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}"
        f"/reset-password?token={quote(reset_token, safe='')}"
    )

    message = EmailMessage()

    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient_email
    message["Subject"] = "FleetPulse Password Reset"

    message.set_content(
        "You requested a FleetPulse password reset.\n\n"
        f"Reset your password using this link:\n{reset_url}\n\n"
        "This link expires in 15 minutes and can only be used once.\n\n"
        "If you did not request this reset, ignore this email."
    )

    
    # Port 465 uses SSL from the beginning.
    if settings.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            context=ssl.create_default_context(),
            timeout=20,
        ) as smtp:
            smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD,
                initial_response_ok=False,
            )
            smtp.send_message(message)

    # Port 587 uses STARTTLS.
    else:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=20,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls(
                context=ssl.create_default_context()
            )
            smtp.ehlo()

            smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD,
                initial_response_ok=False,
            )
            smtp.send_message(message)
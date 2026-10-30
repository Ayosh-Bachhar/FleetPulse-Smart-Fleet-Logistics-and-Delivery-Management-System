import asyncio
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.controllers.accounts.password_reset_controller import (
    router as password_reset_router,
)
from app.services.accounts.password_reset_service import (
    InvalidResetTokenError,
)


def test_password_reset_api_contract():

    async def run_tests():
        app = FastAPI()

        app.include_router(
            password_reset_router,
            prefix="/api/v1",
        )

        base_url = "/api/v1/accounts"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            # Test forgot password
            with (
                patch(
                    "app.controllers.accounts.password_reset_controller.smtp_is_configured",
                    return_value=True,
                ),
                patch(
                    "app.controllers.accounts.password_reset_controller.request_password_reset",
                    new_callable=AsyncMock,
                ) as mock_request,
                patch(
                    "app.controllers.accounts.password_reset_controller.send_password_reset_email",
                ) as mock_email,
            ):
                mock_request.side_effect = [
                    None,
                    "internal-test-token",
                ]

                unknown = await client.post(
                    f"{base_url}/forgot-password",
                    json={"email": "unknown@example.com"},
                )

                known = await client.post(
                    f"{base_url}/forgot-password",
                    json={"email": "known@example.com"},
                )

                assert unknown.status_code == 200
                assert known.status_code == 200
                assert unknown.json() == known.json()

                print("Forgot password endpoint: PASSED")
                print("Account enumeration protection: PASSED")

                mock_email.assert_called_once_with(
                    "known@example.com",
                    "internal-test-token",
                )

                assert "internal-test-token" not in str(
                    known.json()
                )

                print("Email integration: PASSED")
                print("Reset token privacy: PASSED")

                assert (
                    known.headers["cache-control"]
                    == "no-store"
                )

                print("Cache protection: PASSED")

            # Test missing SMTP configuration
            with patch(
                "app.controllers.accounts.password_reset_controller.smtp_is_configured",
                return_value=False,
            ):
                unavailable = await client.post(
                    f"{base_url}/forgot-password",
                    json={"email": "test@example.com"},
                )

                assert unavailable.status_code == 503

                print("SMTP unavailable handling: PASSED")

            # Test password reset endpoint
            with patch(
                "app.controllers.accounts.password_reset_controller.reset_password",
                new_callable=AsyncMock,
            ) as mock_reset:

                valid_token = "a" * 43

                valid = await client.post(
                    f"{base_url}/reset-password",
                    json={
                        "token": valid_token,
                        "new_password": "NewPassword123!",
                    },
                )

                assert valid.status_code == 200

                assert (
                    valid.json()["message"]
                    == "Password reset successfully."
                )

                mock_reset.assert_awaited_once_with(
                    token=valid_token,
                    new_password="NewPassword123!",
                )

                print("Valid password reset: PASSED")

                mock_reset.reset_mock()
                mock_reset.side_effect = InvalidResetTokenError()

                invalid = await client.post(
                    f"{base_url}/reset-password",
                    json={
                        "token": "b" * 43,
                        "new_password": "NewPassword123!",
                    },
                )

                assert invalid.status_code == 400

                print("Invalid token rejection: PASSED")

                mock_reset.reset_mock()
                mock_reset.side_effect = None

                # Invalid input validation
                invalid_cases = [
                    {
                        "token": "short",
                        "new_password": "NewPassword123!",
                    },
                    {
                        "token": "c" * 43,
                        "new_password": "123",
                    },
                    {
                        "token": "c" * 43,
                        "new_password": "x" * 73,
                    },
                    {
                        "token": "c" * 43,
                        "new_password": "NewPassword123!",
                        "role": "admin",
                    },
                ]

                for payload in invalid_cases:
                    response = await client.post(
                        f"{base_url}/reset-password",
                        json=payload,
                    )

                    assert response.status_code == 422

                mock_reset.assert_not_awaited()

                print("Invalid input validation: PASSED")
                print("Role escalation prevention: PASSED")

        print("PASSWORD RESET AUTOMATED TEST PASSED")

    asyncio.run(run_tests())
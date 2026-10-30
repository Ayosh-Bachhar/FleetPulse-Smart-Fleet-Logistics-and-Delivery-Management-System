import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.controllers.accounts.register_controller import (
    router as register_router,
)
from app.schemas.accounts.register_schemas import RegisterResponse
from app.services.accounts.register_service import (
    EmailAlreadyRegisteredError,
)


def test_registration_api_contract():

    async def run_tests():
        app = FastAPI()
        app.include_router(
            register_router,
            prefix="/api/v1",
        )

        url = "/api/v1/accounts/register"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            with patch(
                "app.controllers.accounts.register_controller.register_user",
                new_callable=AsyncMock,
            ) as mock_register:

                mock_register.return_value = RegisterResponse(
                    id="507f1f77bcf86cd799439011",
                    full_name="Test Customer",
                    email="test@example.com",
                    role="customer",
                    created_at=datetime.now(timezone.utc),
                )

                # Successful registration
                response = await client.post(
                    url,
                    json={
                        "full_name": " Test Customer ",
                        "email": "TEST@EXAMPLE.COM",
                        "password": "ValidPassword123!",
                    },
                )

                assert response.status_code == 201

                data = response.json()

                assert data["role"] == "customer"
                assert data["email"] == "test@example.com"
                assert "password" not in data
                assert "password_hash" not in data

                submitted = mock_register.await_args.args[0]
                assert submitted.email == "test@example.com"
                assert submitted.full_name == "Test Customer"

                print("Successful registration: PASSED")
                print("Safe response: PASSED")
                print("Input normalization: PASSED")

                # Duplicate email
                mock_register.side_effect = (
                    EmailAlreadyRegisteredError(
                        "An account with this email already exists."
                    )
                )

                duplicate = await client.post(
                    url,
                    json={
                        "full_name": "Test Customer",
                        "email": "test@example.com",
                        "password": "ValidPassword123!",
                    },
                )

                assert duplicate.status_code == 409

                print("Duplicate email rejection: PASSED")

                # Invalid inputs
                invalid_cases = [
                    {
                        "full_name": "Test Customer",
                        "email": "invalid-email",
                        "password": "ValidPassword123!",
                    },
                    {
                        "full_name": " ",
                        "email": "test@example.com",
                        "password": "ValidPassword123!",
                    },
                    {
                        "full_name": "Test Customer",
                        "email": "test@example.com",
                        "password": "123",
                    },
                    {
                        "full_name": "Test Customer",
                        "email": "test@example.com",
                        "password": "x" * 73,
                    },
                    {
                        "full_name": "Test Customer",
                        "email": "test@example.com",
                        "password": "ValidPassword123!",
                        "role": "admin",
                    },
                ]

                mock_register.reset_mock()

                for payload in invalid_cases:
                    invalid = await client.post(
                        url,
                        json=payload,
                    )

                    assert invalid.status_code == 422

                mock_register.assert_not_awaited()

                print("Invalid input rejection: PASSED")
                print("Role escalation prevention: PASSED")

        print("REGISTRATION AUTOMATED TEST PASSED")

    asyncio.run(run_tests())
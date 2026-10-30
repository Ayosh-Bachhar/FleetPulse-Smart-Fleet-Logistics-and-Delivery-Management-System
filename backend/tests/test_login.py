import asyncio
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.controllers.accounts.login_controller import (
    router as login_router,
)
from app.schemas.accounts.login_schemas import LoginResponse
from app.services.accounts.login_service import (
    InvalidCredentialsError,
)


def test_login_api_contract():

    async def run_tests():
        app = FastAPI()
        app.include_router(login_router, prefix="/api/v1")

        login_url = "/api/v1/accounts/login"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            with patch(
                "app.controllers.accounts.login_controller.login_user",
                new_callable=AsyncMock,
            ) as mock_login:

                mock_login.return_value = (
                    LoginResponse(
                        id="507f1f77bcf86cd799439011",
                        full_name="Test Customer",
                        email="test@example.com",
                        role="customer",
                    ),
                    "test.jwt.token",
                )

                response = await client.post(
                    login_url,
                    json={
                        "email": "test@example.com",
                        "password": "ValidPassword123!",
                    },
                )

                assert response.status_code == 200
                assert response.json()["role"] == "customer"
                assert "access_token" not in response.json()
                assert "password_hash" not in response.json()

                print("Successful login response: PASSED")

                cookie = response.headers["set-cookie"].lower()

                assert "httponly" in cookie
                assert "samesite=lax" in cookie
                assert "path=/api/v1" in cookie

                print("Authentication cookie: PASSED")

                mock_login.side_effect = InvalidCredentialsError()

                invalid = await client.post(
                    login_url,
                    json={
                        "email": "test@example.com",
                        "password": "WrongPassword",
                    },
                )

                assert invalid.status_code == 401
                print("Invalid credentials rejection: PASSED")

                bad_input = await client.post(
                    login_url,
                    json={
                        "email": "invalid-email",
                        "password": "SomePassword123",
                    },
                )

                assert bad_input.status_code == 422
                print("Invalid input validation: PASSED")

            unauthenticated = await client.get(
                "/api/v1/accounts/me"
            )

            assert unauthenticated.status_code == 401
            print("Unauthenticated access rejection: PASSED")

        print("LOGIN AUTOMATED TEST PASSED")

    asyncio.run(run_tests())
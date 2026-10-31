import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.controllers.driver_management_controller import (
    router as driver_router,
)
from app.core.access_control import (
    get_current_user,
    require_csrf,
)
from app.models.user import Role
from app.models.driver import (
    Driver,
    DriverLicenseClass,
    DriverStatus,
)
from app.models.vehicle import VehicleStatus

from app.schemas.driver_management_schemas import (
    DriverCreate,
    DriverUpdate,
    DriverResponse,
    DriverListResponse,
    DriverCompatibilityResponse,
)

from app.services.driver_management_service import (
    DriverAlreadyExistsError,
    DriverNotFoundError,
    allowed_vehicle_types,
    is_license_compatible,
    evaluate_driver_vehicle,
)


URL = "/api/v1/drivers"
DRIVER_ID = "507f1f77bcf86cd799439011"
VEHICLE_ID = "507f1f77bcf86cd799439012"


def driver_data():
    return {
        "full_name": "Test Driver",
        "phone": "+8801700000000",
        "license_number": "DL-TEST-001",
        "license_class": "heavy",
        "license_expiry": (
            date.today() + timedelta(days=365)
        ).isoformat(),
        "status": "available",
    }


def sample_response():
    values = driver_data()

    return DriverResponse(
        id=DRIVER_ID,
        **values,
        user_id=None,
        linked_user_email=None,
        allowed_vehicle_types=[
            "Mini Van",
            "Van",
            "Truck",
        ],
        license_valid=True,
        is_available=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


def make_app(role=None, bypass_csrf=True):
    app = FastAPI()
    app.include_router(driver_router, prefix="/api/v1")

    if role is not None:
        app.dependency_overrides[get_current_user] = (
            lambda: SimpleNamespace(role=role)
        )

    if bypass_csrf:
        app.dependency_overrides[require_csrf] = lambda: None

    return app


def test_driver_model_construct_without_database():
    driver = Driver.model_construct(
        full_name="Test Driver",
        license_number="DL-TEST-001",
        license_class=DriverLicenseClass.HEAVY,
        license_expiry=date.today(),
        status=DriverStatus.AVAILABLE,
    )

    assert driver.license_class == DriverLicenseClass.HEAVY
    assert driver.status == DriverStatus.AVAILABLE


def test_license_number_normalization():
    data = DriverCreate(
        **{
            **driver_data(),
            "license_number": " dl-test-001 ",
        }
    )

    assert data.license_number == "DL-TEST-001"


def test_invalid_driver_input():
    with pytest.raises(ValidationError):
        DriverCreate(
            **{
                **driver_data(),
                "full_name": " ",
            }
        )

    with pytest.raises(ValidationError):
        DriverCreate(
            **{
                **driver_data(),
                "license_class": "unknown",
            }
        )

    with pytest.raises(ValidationError):
        DriverCreate(
            **{
                **driver_data(),
                "license_number": "!",
            }
        )


def test_empty_update_rejected():
    with pytest.raises(ValidationError):
        DriverUpdate()

    with pytest.raises(ValidationError):
        DriverUpdate(license_expiry=None)


def test_license_compatibility():
    assert allowed_vehicle_types(
        DriverLicenseClass.LIGHT
    ) == ["Mini Van"]

    assert is_license_compatible(
        DriverLicenseClass.HEAVY,
        "Truck",
    )

    assert not is_license_compatible(
        DriverLicenseClass.LIGHT,
        "Truck",
    )


def test_driver_vehicle_eligibility():
    driver = SimpleNamespace(
        license_class=DriverLicenseClass.HEAVY,
        license_expiry=date.today() + timedelta(days=30),
        status=DriverStatus.AVAILABLE,
    )

    vehicle = SimpleNamespace(
        vehicle_type="Truck",
        status=VehicleStatus.AVAILABLE,
    )

    compatible, eligible, _ = evaluate_driver_vehicle(
        driver,
        vehicle,
    )

    assert compatible
    assert eligible

    vehicle.status = VehicleStatus.MAINTENANCE

    compatible, eligible, _ = evaluate_driver_vehicle(
        driver,
        vehicle,
    )

    assert compatible
    assert not eligible

    vehicle.status = VehicleStatus.AVAILABLE
    driver.license_expiry = date.today() - timedelta(days=1)

    compatible, eligible, _ = evaluate_driver_vehicle(
        driver,
        vehicle,
    )

    assert compatible
    assert not eligible

    driver.license_expiry = date.today() + timedelta(days=30)
    driver.status = DriverStatus.INACTIVE

    compatible, eligible, _ = evaluate_driver_vehicle(
        driver,
        vehicle,
    )

    assert compatible
    assert not eligible


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER],
)
def test_staff_can_list_drivers(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.driver_management_controller.list_drivers",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = DriverListResponse(
                items=[sample_response()],
                total=1,
                page=1,
                page_size=10,
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(URL)

            assert response.status_code == 200
            assert response.json()["total"] == 1
            mocked.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DRIVER],
)
def test_non_staff_access_denied(role):
    async def run():
        app = make_app(role)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 403

    asyncio.run(run())


def test_unauthenticated_access_denied():
    async def run():
        app = make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 401

    asyncio.run(run())


def test_staff_can_create_driver():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.driver_management_controller.create_driver",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=driver_data(),
                )

            assert response.status_code == 201
            assert response.json()["license_class"] == "heavy"
            mocked.assert_awaited_once()

    asyncio.run(run())


def test_duplicate_license_returns_409():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.driver_management_controller.create_driver",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = DriverAlreadyExistsError(
                "License already exists."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=driver_data(),
                )

            assert response.status_code == 409

    asyncio.run(run())


def test_missing_driver_returns_404():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.driver_management_controller.get_driver",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = DriverNotFoundError(
                "Driver not found."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    f"{URL}/{DRIVER_ID}"
                )

            assert response.status_code == 404

    asyncio.run(run())


def test_update_driver():
    async def run():
        app = make_app(Role.DISPATCHER)

        updated = sample_response().model_copy(
            update={
                "status": DriverStatus.INACTIVE,
                "is_available": False,
            }
        )

        with patch(
            "app.controllers.driver_management_controller.update_driver",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = updated

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.patch(
                    f"{URL}/{DRIVER_ID}",
                    json={"status": "inactive"},
                )

            assert response.status_code == 200
            assert response.json()["status"] == "inactive"

    asyncio.run(run())


def test_vehicle_compatibility_endpoint():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.driver_management_controller."
            "check_driver_compatibility",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = DriverCompatibilityResponse(
                driver_id=DRIVER_ID,
                vehicle_id=VEHICLE_ID,
                license_compatible=True,
                eligible_for_dispatch=True,
                reason="Driver and vehicle are compatible.",
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    f"{URL}/{DRIVER_ID}/compatibility/"
                    f"{VEHICLE_ID}"
                )

            assert response.status_code == 200
            assert response.json()["eligible_for_dispatch"]

    asyncio.run(run())


def test_driver_write_requires_csrf():
    async def run():
        app = make_app(
            Role.ADMIN,
            bypass_csrf=False,
        )

        with patch(
            "app.controllers.driver_management_controller.create_driver",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=driver_data(),
                )

            assert response.status_code == 403
            mocked.assert_not_awaited()

    asyncio.run(run())
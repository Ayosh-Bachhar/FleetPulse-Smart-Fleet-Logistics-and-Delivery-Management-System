import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.controllers.fleet_management_controller import (
    router as fleet_router,
)
from app.core.access_control import (
    get_current_user,
    require_csrf,
)
from app.models.user import Role
from app.models.vehicle import Vehicle, VehicleStatus
from app.schemas.fleet_management_schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VehicleListResponse,
)
from app.services.fleet_management_service import (
    VehicleAlreadyExistsError,
    VehicleNotFoundError,
)


URL = "/api/v1/vehicles"
VEHICLE_ID = "507f1f77bcf86cd799439011"


def vehicle_data():
    return {
        "registration_number": "FP-TEST-001",
        "vehicle_type": "Truck",
        "capacity_kg": 3500,
        "volume_capacity_m3": 20,
        "fuel_type": "Diesel",
        "status": "available",
    }


def sample_response():
    return VehicleResponse(
        id=VEHICLE_ID,
        **vehicle_data(),
        is_available=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


def make_app(role=None, bypass_csrf=True):
    app = FastAPI()
    app.include_router(fleet_router, prefix="/api/v1")

    if role is not None:
        app.dependency_overrides[get_current_user] = (
            lambda: SimpleNamespace(role=role)
        )

    if bypass_csrf:
        app.dependency_overrides[require_csrf] = lambda: None

    return app


def test_vehicle_model_accepts_existing_seed_data():
    vehicle = Vehicle.model_construct(
        registration_number="FP-DEMO-001",
        vehicle_type="Truck",
        capacity_kg=3500,
        status=VehicleStatus.AVAILABLE,
    )

    assert vehicle.volume_capacity_m3 is None
    assert vehicle.fuel_type is None
    assert vehicle.status == VehicleStatus.AVAILABLE


def test_registration_is_normalized():
    data = VehicleCreate(
        **{
            **vehicle_data(),
            "registration_number": " fp-test-001 ",
        }
    )

    assert data.registration_number == "FP-TEST-001"


def test_invalid_capacity_rejected():
    for invalid_weight in [0, -10]:
        with pytest.raises(ValidationError):
            VehicleCreate(
                **{
                    **vehicle_data(),
                    "capacity_kg": invalid_weight,
                }
            )

    with pytest.raises(ValidationError):
        VehicleCreate(
            **{
                **vehicle_data(),
                "volume_capacity_m3": 0,
            }
        )


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        VehicleCreate(
            **{
                **vehicle_data(),
                "status": "unknown",
            }
        )


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        VehicleCreate(
            **{
                **vehicle_data(),
                "admin_override": True,
            }
        )


def test_empty_update_rejected():
    with pytest.raises(ValidationError):
        VehicleUpdate()

    with pytest.raises(ValidationError):
        VehicleUpdate(status=None)


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER],
)
def test_staff_can_list_vehicles(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.fleet_management_controller.list_vehicles",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = VehicleListResponse(
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
            assert len(response.json()["items"]) == 1
            mocked.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DRIVER],
)
def test_non_staff_cannot_access_fleet(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.fleet_management_controller.list_vehicles",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(URL)

            assert response.status_code == 403
            mocked.assert_not_awaited()

    asyncio.run(run())


def test_unauthenticated_fleet_access_rejected():
    async def run():
        app = make_app(role=None)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 401

    asyncio.run(run())


def test_staff_can_create_vehicle():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.fleet_management_controller.create_vehicle",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=vehicle_data(),
                )

            assert response.status_code == 201
            assert response.json()["status"] == "available"
            assert response.json()["is_available"] is True
            mocked.assert_awaited_once()

    asyncio.run(run())


def test_duplicate_registration_returns_409():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.fleet_management_controller.create_vehicle",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = VehicleAlreadyExistsError(
                "Vehicle already exists."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=vehicle_data(),
                )

            assert response.status_code == 409

    asyncio.run(run())


def test_missing_vehicle_returns_404():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.fleet_management_controller.get_vehicle",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = VehicleNotFoundError(
                "Vehicle not found."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    f"{URL}/{VEHICLE_ID}"
                )

            assert response.status_code == 404

    asyncio.run(run())


def test_staff_can_update_vehicle():
    async def run():
        app = make_app(Role.DISPATCHER)

        updated = sample_response().model_copy(
            update={
                "status": VehicleStatus.MAINTENANCE,
                "is_available": False,
            }
        )

        with patch(
            "app.controllers.fleet_management_controller.update_vehicle",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = updated

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.patch(
                    f"{URL}/{VEHICLE_ID}",
                    json={"status": "maintenance"},
                )

            assert response.status_code == 200
            assert response.json()["is_available"] is False
            assert response.json()["status"] == "maintenance"

    asyncio.run(run())


def test_write_requires_csrf():
    async def run():
        app = make_app(
            Role.ADMIN,
            bypass_csrf=False,
        )

        with patch(
            "app.controllers.fleet_management_controller.create_vehicle",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=vehicle_data(),
                )

            assert response.status_code == 403
            mocked.assert_not_awaited()

    asyncio.run(run())
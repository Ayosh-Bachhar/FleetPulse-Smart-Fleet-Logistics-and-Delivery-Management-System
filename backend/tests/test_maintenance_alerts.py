import asyncio

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId

import pytest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.controllers.maintenance_alerts_controller import (
    router as maintenance_router,
)

from app.core.access_control import (
    get_current_user,
    require_csrf,
)

from app.models.user import Role
from app.models.vehicle import (
    Vehicle,
    VehicleStatus,
    is_vehicle_maintenance_due,
    is_vehicle_dispatchable,
)

from app.schemas.maintenance_alerts_schemas import (
    AddMileageRequest,
    CompleteServiceRequest,
    ChangeServiceIntervalRequest,
    MaintenanceVehicleResponse,
    MaintenanceListResponse,
    MaintenanceHistoryResponse,
)

from app.services.maintenance_alerts_service import (
    MaintenanceOperationError,
    MaintenanceVehicleNotFoundError,
    apply_distance,
    apply_interval_change,
    apply_service_completion,
    maintenance_to_response,
)


URL = "/api/v1/maintenance"
VEHICLE_ID = "507f1f77bcf86cd799439011"
USER_ID = "507f1f77bcf86cd799439012"


def fake_vehicle(
    odometer=0,
    last_service=0,
    interval=5000,
    due=False,
    status=VehicleStatus.AVAILABLE,
):
    return SimpleNamespace(
        id=ObjectId(VEHICLE_ID),
        registration_number="FP-DEMO-001",
        vehicle_type="Truck",
        odometer_km=odometer,
        last_service_km=last_service,
        service_interval_km=interval,
        maintenance_due=due,
        status=status,
        updated_at=None,
    )


def sample_response():
    return maintenance_to_response(fake_vehicle())


def make_app(role=None, bypass_csrf=True):
    app = FastAPI()
    app.include_router(
        maintenance_router,
        prefix="/api/v1",
    )

    if role is not None:
        app.dependency_overrides[get_current_user] = (
            lambda: SimpleNamespace(
                id=ObjectId(USER_ID),
                role=role,
            )
        )

    if bypass_csrf:
        app.dependency_overrides[require_csrf] = lambda: None

    return app


def test_existing_vehicle_model_defaults():
    vehicle = Vehicle.model_construct(
        registration_number="FP-DEMO-001",
        vehicle_type="Truck",
        capacity_kg=3500,
        status=VehicleStatus.AVAILABLE,
    )

    assert vehicle.odometer_km == 0
    assert vehicle.last_service_km == 0
    assert vehicle.service_interval_km == 5000
    assert vehicle.maintenance_due is False
    assert is_vehicle_dispatchable(vehicle)


def test_invalid_mileage_rejected():
    for distance in (0, -1, 10001, float("inf")):
        with pytest.raises(ValidationError):
            AddMileageRequest(distance_km=distance)


def test_invalid_interval_rejected():
    for interval in (0, -10, 100001):
        with pytest.raises(ValidationError):
            ChangeServiceIntervalRequest(
                service_interval_km=interval
            )


def test_service_requires_notes():
    with pytest.raises(ValidationError):
        CompleteServiceRequest(notes=" ")

    with pytest.raises(ValidationError):
        CompleteServiceRequest(notes="ab")


def test_mileage_below_threshold():
    vehicle = fake_vehicle(odometer=4500)

    triggered = apply_distance(vehicle, 100)

    assert triggered is False
    assert vehicle.odometer_km == 4600
    assert vehicle.maintenance_due is False
    assert is_vehicle_dispatchable(vehicle)


def test_mileage_at_threshold_triggers_maintenance():
    vehicle = fake_vehicle(odometer=4900)

    triggered = apply_distance(vehicle, 100)

    assert triggered is True
    assert vehicle.odometer_km == 5000
    assert vehicle.maintenance_due is True
    assert vehicle.status == VehicleStatus.MAINTENANCE
    assert not is_vehicle_dispatchable(vehicle)


def test_mileage_above_threshold_stays_due():
    vehicle = fake_vehicle(
        odometer=5000,
        due=True,
        status=VehicleStatus.MAINTENANCE,
    )

    triggered = apply_distance(vehicle, 50)

    assert triggered is False
    assert vehicle.odometer_km == 5050
    assert vehicle.maintenance_due is True


def test_interval_reduction_can_trigger_service():
    vehicle = fake_vehicle(odometer=4000)

    triggered = apply_interval_change(vehicle, 3000)

    assert triggered is True
    assert vehicle.maintenance_due is True
    assert vehicle.status == VehicleStatus.MAINTENANCE


def test_increasing_interval_does_not_clear_due():
    vehicle = fake_vehicle(
        odometer=5000,
        due=True,
        status=VehicleStatus.MAINTENANCE,
    )

    apply_interval_change(vehicle, 10000)

    assert vehicle.maintenance_due is True
    assert not is_vehicle_dispatchable(vehicle)


def test_service_completion_clears_due():
    vehicle = fake_vehicle(
        odometer=5500,
        due=True,
        status=VehicleStatus.MAINTENANCE,
    )

    apply_service_completion(vehicle)

    assert vehicle.last_service_km == 5500
    assert vehicle.maintenance_due is False
    assert vehicle.status == VehicleStatus.AVAILABLE
    assert is_vehicle_dispatchable(vehicle)


def test_service_keeps_inactive_vehicle_inactive():
    vehicle = fake_vehicle(
        odometer=5500,
        due=True,
        status=VehicleStatus.INACTIVE,
    )

    apply_service_completion(vehicle)

    assert vehicle.maintenance_due is False
    assert vehicle.status == VehicleStatus.INACTIVE
    assert not is_vehicle_dispatchable(vehicle)


def test_cannot_service_vehicle_in_use():
    vehicle = fake_vehicle(
        status=VehicleStatus.IN_USE
    )

    with pytest.raises(MaintenanceOperationError):
        apply_service_completion(vehicle)


def test_maintenance_response_calculation():
    vehicle = fake_vehicle(
        odometer=2500,
        interval=5000,
    )

    response = maintenance_to_response(vehicle)

    assert response.kilometers_since_service == 2500
    assert response.kilometers_until_service == 2500
    assert response.service_progress_percent == 50
    assert not response.needs_attention


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER],
)
def test_staff_can_list_maintenance(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.maintenance_alerts_controller."
            "list_maintenance",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = MaintenanceListResponse(
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
def test_non_staff_cannot_access_maintenance(role):
    async def run():
        app = make_app(role)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 403

    asyncio.run(run())


def test_unauthenticated_access_rejected():
    async def run():
        app = make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 401

    asyncio.run(run())


def test_add_distance_endpoint():
    async def run():
        app = make_app(Role.ADMIN)

        updated = maintenance_to_response(
            fake_vehicle(odometer=250)
        )

        with patch(
            "app.controllers.maintenance_alerts_controller."
            "add_vehicle_distance",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = updated

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    f"{URL}/{VEHICLE_ID}/distance",
                    json={"distance_km": 250},
                )

            assert response.status_code == 200
            assert response.json()["odometer_km"] == 250
            mocked.assert_awaited_once()

    asyncio.run(run())


def test_complete_service_endpoint():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.maintenance_alerts_controller."
            "complete_vehicle_service",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    f"{URL}/{VEHICLE_ID}/complete-service",
                    json={"notes": "Vehicle serviced"},
                )

            assert response.status_code == 200
            assert response.json()["maintenance_due"] is False

    asyncio.run(run())


def test_missing_vehicle_returns_404():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.maintenance_alerts_controller."
            "get_maintenance",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = MaintenanceVehicleNotFoundError(
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


def test_in_use_service_returns_409():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.maintenance_alerts_controller."
            "complete_vehicle_service",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = MaintenanceOperationError(
                "Vehicle is in use."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    f"{URL}/{VEHICLE_ID}/complete-service",
                    json={"notes": "Routine service"},
                )

            assert response.status_code == 409

    asyncio.run(run())


def test_write_requires_csrf():
    async def run():
        app = make_app(
            Role.ADMIN,
            bypass_csrf=False,
        )

        with patch(
            "app.controllers.maintenance_alerts_controller."
            "add_vehicle_distance",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    f"{URL}/{VEHICLE_ID}/distance",
                    json={"distance_km": 100},
                )

            assert response.status_code == 403
            mocked.assert_not_awaited()

    asyncio.run(run())
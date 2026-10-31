import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.access_control import (
    get_current_user,
    require_csrf,
)
from app.controllers.dispatch_planning_controller import (
    router as dispatch_router,
)
from app.models.user import Role
from app.models.driver import (
    DriverLicenseClass,
    DriverStatus,
)
from app.models.vehicle import VehicleStatus
from app.models.shift import ShiftStatus
from app.models.order import Order, OrderStatus
from app.models.trip import TripStatus

from app.schemas.dispatch_planning_schemas import (
    DispatchRequest,
    DispatchOrderResponse,
    DispatchOrderListResponse,
    TripResponse,
    TripListResponse,
)

from app.services.dispatch_planning_service import (
    DispatchValidationError,
    DispatchConflictError,
    calculate_dispatch_load,
    check_dispatch_resources,
    validate_dispatch_orders,
    periods_overlap,
)


SHIFT_ID = "507f1f77bcf86cd799439010"
DRIVER_ID = "507f1f77bcf86cd799439011"
VEHICLE_ID = "507f1f77bcf86cd799439012"
TRIP_ID = "507f1f77bcf86cd799439013"
ORDER_1 = "507f1f77bcf86cd799439014"
ORDER_2 = "507f1f77bcf86cd799439015"
USER_ID = "507f1f77bcf86cd799439016"

URL = "/api/v1/trips"


def dispatch_data():
    return {
        "shift_id": SHIFT_ID,
        "order_ids": [ORDER_1, ORDER_2],
    }


def sample_order(
    weight=100,
    volume=1,
    status=OrderStatus.WAREHOUSE,
    trip_id=None,
):
    return SimpleNamespace(
        reference_code="FP-TEST-001",
        weight_kg=weight,
        length_cm=100,
        width_cm=100,
        height_cm=100,
        volume_m3=volume,
        status=status,
        trip_id=trip_id,
    )


def sample_vehicle():
    return SimpleNamespace(
        id=ObjectId(VEHICLE_ID),
        registration_number="FP-DEMO-001",
        vehicle_type="Truck",
        capacity_kg=3500,
        volume_capacity_m3=20,
        status=VehicleStatus.AVAILABLE,
        maintenance_due=False,
        odometer_km=0,
        last_service_km=0,
        service_interval_km=5000,
    )


def sample_driver():
    return SimpleNamespace(
        id=ObjectId(DRIVER_ID),
        full_name="Test Driver",
        license_class=DriverLicenseClass.HEAVY,
        license_expiry=date(2040, 1, 1),
        status=DriverStatus.AVAILABLE,
        user_id=None,
    )


def sample_shift():
    start = datetime(
        2035, 1, 1, 9,
        tzinfo=timezone(timedelta(hours=6)),
    )

    return SimpleNamespace(
        id=ObjectId(SHIFT_ID),
        driver_id=ObjectId(DRIVER_ID),
        vehicle_id=ObjectId(VEHICLE_ID),
        start_at=start,
        end_at=start + timedelta(hours=8),
        status=ShiftStatus.SCHEDULED,
    )


def sample_trip_response():
    start = datetime(
        2035, 1, 1, 3,
        tzinfo=timezone.utc,
    )

    return TripResponse(
        id=TRIP_ID,
        order_ids=[ORDER_1, ORDER_2],
        order_count=2,
        order_references=[
            "FP-TEST-001",
            "FP-TEST-002",
        ],
        driver_id=DRIVER_ID,
        driver_name="Test Driver",
        vehicle_id=VEHICLE_ID,
        vehicle_registration="FP-DEMO-001",
        vehicle_type="Truck",
        shift_id=SHIFT_ID,
        start_at=start,
        end_at=start + timedelta(hours=8),
        total_weight_kg=250,
        total_volume_m3=1.5,
        status=TripStatus.DISPATCHED,
        estimated_distance_km=None,
        actual_distance_km=None,
        created_by=USER_ID,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
        completed_at=None,
        cancelled_at=None,
    )


def make_app(role=None, bypass_csrf=True):
    app = FastAPI()
    app.include_router(
        dispatch_router,
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


def test_order_model_construct_without_database():
    order = Order.model_construct(
        customer_id=ObjectId(USER_ID),
        pickup_address="Uttara, Dhaka",
        delivery_address="Mirpur, Dhaka",
        weight_kg=100,
        length_cm=100,
        width_cm=100,
        height_cm=100,
        volume_m3=1,
        status=OrderStatus.WAREHOUSE,
    )

    assert order.trip_id is None
    assert order.status == OrderStatus.WAREHOUSE


def test_dispatch_request_accepts_multiple_orders():
    data = DispatchRequest(**dispatch_data())

    assert len(data.order_ids) == 2


def test_invalid_dispatch_requests():
    with pytest.raises(ValidationError):
        DispatchRequest(
            shift_id="invalid",
            order_ids=[ORDER_1],
        )

    with pytest.raises(ValidationError):
        DispatchRequest(
            shift_id=SHIFT_ID,
            order_ids=[],
        )

    with pytest.raises(ValidationError):
        DispatchRequest(
            shift_id=SHIFT_ID,
            order_ids=[ORDER_1, ORDER_1],
        )


def test_capacity_accepts_valid_orders():
    orders = [
        sample_order(weight=200),
        sample_order(weight=150),
    ]

    weight, volume = calculate_dispatch_load(
        orders,
        sample_vehicle(),
    )

    assert weight == 350
    assert volume == 2


def test_capacity_blocks_weight_overrun():
    vehicle = sample_vehicle()
    vehicle.capacity_kg = 100

    with pytest.raises(
        DispatchValidationError,
        match="weight",
    ):
        calculate_dispatch_load(
            [sample_order(weight=150)],
            vehicle,
        )


def test_capacity_blocks_volume_overrun():
    vehicle = sample_vehicle()
    vehicle.volume_capacity_m3 = 0.5

    with pytest.raises(
        DispatchValidationError,
        match="volume",
    ):
        calculate_dispatch_load(
            [sample_order(volume=1)],
            vehicle,
        )


def test_missing_volume_capacity_blocks_dispatch():
    vehicle = sample_vehicle()
    vehicle.volume_capacity_m3 = None

    with pytest.raises(
        DispatchValidationError,
        match="volume capacity",
    ):
        calculate_dispatch_load(
            [sample_order()],
            vehicle,
        )


def test_unready_order_is_rejected():
    with pytest.raises(
        DispatchValidationError,
        match="Warehouse",
    ):
        validate_dispatch_orders([
            sample_order(status=OrderStatus.PLACED)
        ])


def test_already_assigned_order_is_rejected():
    with pytest.raises(
        DispatchConflictError,
        match="already assigned",
    ):
        validate_dispatch_orders([
            sample_order(trip_id=ObjectId(TRIP_ID))
        ])


def test_license_compatibility_is_checked():
    driver = sample_driver()
    driver.license_class = DriverLicenseClass.LIGHT

    with pytest.raises(
        DispatchValidationError,
        match="license class",
    ):
        check_dispatch_resources(
            driver,
            sample_vehicle(),
            sample_shift(),
        )


def test_service_due_vehicle_is_rejected():
    vehicle = sample_vehicle()
    vehicle.maintenance_due = True

    with pytest.raises(
        DispatchValidationError,
        match="maintenance",
    ):
        check_dispatch_resources(
            sample_driver(),
            vehicle,
            sample_shift(),
        )


def test_unscheduled_shift_is_rejected():
    shift = sample_shift()
    shift.status = ShiftStatus.CANCELLED

    with pytest.raises(
        DispatchValidationError,
        match="scheduled",
    ):
        check_dispatch_resources(
            sample_driver(),
            sample_vehicle(),
            shift,
        )


def test_license_expiry_blocks_dispatch():
    driver = sample_driver()
    driver.license_expiry = date(2030, 1, 1)

    with pytest.raises(
        DispatchValidationError,
        match="expires",
    ):
        check_dispatch_resources(
            driver,
            sample_vehicle(),
            sample_shift(),
        )


def test_valid_shift_is_accepted():
    start, end = check_dispatch_resources(
        sample_driver(),
        sample_vehicle(),
        sample_shift(),
    )

    assert start < end


def test_trip_overlap_rule():
    start = datetime(
        2035, 1, 1, 9,
        tzinfo=timezone.utc,
    )

    end = start + timedelta(hours=8)

    assert periods_overlap(
        start,
        end,
        start + timedelta(hours=2),
        end + timedelta(hours=2),
    )

    assert not periods_overlap(
        start,
        end,
        end,
        end + timedelta(hours=4),
    )


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER],
)
def test_staff_can_view_trips(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.dispatch_planning_controller."
            "list_trips",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = TripListResponse(
                items=[sample_trip_response()],
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

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DRIVER],
)
def test_non_staff_cannot_access_dispatch(role):
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


def test_dispatcher_can_create_trip():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.dispatch_planning_controller."
            "dispatch_trip",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_trip_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=dispatch_data(),
                )

            assert response.status_code == 201
            assert response.json()["order_count"] == 2

    asyncio.run(run())


def test_admin_cannot_dispatch():
    async def run():
        app = make_app(Role.ADMIN)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                URL,
                json=dispatch_data(),
            )

        assert response.status_code == 403

    asyncio.run(run())


def test_dispatch_conflict_returns_409():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.dispatch_planning_controller."
            "dispatch_trip",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = DispatchConflictError(
                "Conflicting trip."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=dispatch_data(),
                )

            assert response.status_code == 409

    asyncio.run(run())


def test_complete_trip_endpoint():
    async def run():
        app = make_app(Role.DISPATCHER)

        completed = sample_trip_response().model_copy(
            update={"status": TripStatus.COMPLETED}
        )

        with patch(
            "app.controllers.dispatch_planning_controller."
            "complete_trip",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = completed

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    f"{URL}/{TRIP_ID}/complete",
                    json={"actual_distance_km": 35},
                )

            assert response.status_code == 200
            assert response.json()["status"] == "completed"

    asyncio.run(run())


def test_write_requires_csrf():
    async def run():
        app = make_app(
            Role.DISPATCHER,
            bypass_csrf=False,
        )

        with patch(
            "app.controllers.dispatch_planning_controller."
            "dispatch_trip",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=dispatch_data(),
                )

            assert response.status_code == 403
            mocked.assert_not_awaited()

    asyncio.run(run())
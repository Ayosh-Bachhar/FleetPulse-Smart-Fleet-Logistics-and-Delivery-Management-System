import asyncio
from datetime import datetime, timezone
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
from app.controllers.order_lifecycle_controller import (
    router,
)
from app.models.order import OrderStatus
from app.models.trip import TripStatus
from app.models.user import Role

from app.schemas.order_lifecycle_schemas import (
    OrderStatusChange,
    OrderLifecycleResponse,
    OrderLifecycleListResponse,
)

from app.services.order_lifecycle_service import (
    LifecycleNotFoundError,
    LifecyclePermissionError,
    LifecycleConflictError,
    allowed_next_status,
    build_lifecycle_filter,
    validate_transition,
    authorize_order_view,
    change_order_status,
)


CUSTOMER_ID = ObjectId(
    "507f1f77bcf86cd799439011"
)
OTHER_CUSTOMER_ID = ObjectId(
    "507f1f77bcf86cd799439012"
)
ORDER_ID = ObjectId(
    "507f1f77bcf86cd799439013"
)
TRIP_ID = ObjectId(
    "507f1f77bcf86cd799439014"
)
DRIVER_ID = ObjectId(
    "507f1f77bcf86cd799439015"
)
USER_ID = ObjectId(
    "507f1f77bcf86cd799439016"
)

BASE_URL = "/api/v1/order-lifecycle/orders"


def fake_user(role):
    return SimpleNamespace(
        id=USER_ID,
        role=role,
    )


def fake_order(
    status=OrderStatus.PLACED,
    trip_id=None,
):
    return SimpleNamespace(
        id=ORDER_ID,
        customer_id=CUSTOMER_ID,
        reference_code="FP-F9-TEST",
        pickup_address="Uttara, Dhaka",
        delivery_address="Mirpur, Dhaka",
        status=status,
        trip_id=trip_id,
        is_rush=False,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


def fake_trip(
    status=TripStatus.DISPATCHED,
    driver_id=DRIVER_ID,
):
    return SimpleNamespace(
        id=TRIP_ID,
        status=status,
        driver_id=driver_id,
        order_ids=[ORDER_ID],
    )


def fake_driver(driver_id=DRIVER_ID):
    return SimpleNamespace(
        id=driver_id,
        user_id=USER_ID,
    )


def fake_response(
    status=OrderStatus.PLACED,
    next_status=OrderStatus.WAREHOUSE,
):
    return OrderLifecycleResponse(
        id=str(ORDER_ID),
        reference_code="FP-F9-TEST",
        pickup_address="Uttara, Dhaka",
        delivery_address="Mirpur, Dhaka",
        status=status,
        trip_id=None,
        is_rush=False,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
        allowed_next_status=next_status,
    )


def make_app(role=None, skip_csrf=True):
    app = FastAPI()

    app.include_router(
        router,
        prefix="/api/v1",
    )

    if role is not None:
        app.dependency_overrides[
            get_current_user
        ] = lambda: fake_user(role)

    if skip_csrf:
        app.dependency_overrides[
            require_csrf
        ] = lambda: None

    return app


def test_schema_accepts_warehouse():
    data = OrderStatusChange(
        status="warehouse"
    )

    assert data.status == OrderStatus.WAREHOUSE


def test_schema_accepts_out_for_delivery():
    data = OrderStatusChange(
        status="out_for_delivery"
    )

    assert data.status == OrderStatus.OUT_FOR_DELIVERY


def test_schema_blocks_delivered():
    with pytest.raises(ValidationError):
        OrderStatusChange(status="delivered")


def test_schema_blocks_extra_fields():
    with pytest.raises(ValidationError):
        OrderStatusChange(
            status="warehouse",
            trip_id=str(TRIP_ID),
        )


def test_dispatcher_can_prepare_placed_order():
    validate_transition(
        fake_order(),
        OrderStatus.WAREHOUSE,
        Role.DISPATCHER,
    )


def test_driver_cannot_prepare_order():
    with pytest.raises(LifecyclePermissionError):
        validate_transition(
            fake_order(),
            OrderStatus.WAREHOUSE,
            Role.DRIVER,
        )


def test_cannot_skip_warehouse():
    with pytest.raises(LifecycleConflictError):
        validate_transition(
            fake_order(),
            OrderStatus.OUT_FOR_DELIVERY,
            Role.DISPATCHER,
        )


def test_cannot_move_warehouse_without_trip():
    with pytest.raises(LifecycleConflictError):
        validate_transition(
            fake_order(OrderStatus.WAREHOUSE),
            OrderStatus.OUT_FOR_DELIVERY,
            Role.DISPATCHER,
        )


def test_dispatcher_can_start_assigned_delivery():
    validate_transition(
        fake_order(
            OrderStatus.WAREHOUSE,
            TRIP_ID,
        ),
        OrderStatus.OUT_FOR_DELIVERY,
        Role.DISPATCHER,
        fake_trip(),
    )


def test_assigned_driver_can_start_delivery():
    validate_transition(
        fake_order(
            OrderStatus.WAREHOUSE,
            TRIP_ID,
        ),
        OrderStatus.OUT_FOR_DELIVERY,
        Role.DRIVER,
        fake_trip(),
        fake_driver(),
    )


def test_other_driver_cannot_start_delivery():
    other_driver = fake_driver(
        ObjectId(
            "507f1f77bcf86cd799439017"
        )
    )

    with pytest.raises(LifecyclePermissionError):
        validate_transition(
            fake_order(
                OrderStatus.WAREHOUSE,
                TRIP_ID,
            ),
            OrderStatus.OUT_FOR_DELIVERY,
            Role.DRIVER,
            fake_trip(),
            other_driver,
        )


@pytest.mark.parametrize(
    "trip_status",
    [
        TripStatus.COMPLETED,
        TripStatus.CANCELLED,
    ],
)
def test_finished_trip_cannot_start_delivery(
    trip_status,
):
    with pytest.raises(LifecycleConflictError):
        validate_transition(
            fake_order(
                OrderStatus.WAREHOUSE,
                TRIP_ID,
            ),
            OrderStatus.OUT_FOR_DELIVERY,
            Role.DISPATCHER,
            fake_trip(status=trip_status),
        )


def test_cannot_move_backwards():
    with pytest.raises(LifecycleConflictError):
        validate_transition(
            fake_order(
                OrderStatus.OUT_FOR_DELIVERY,
                TRIP_ID,
            ),
            OrderStatus.WAREHOUSE,
            Role.DISPATCHER,
        )


def test_f9_cannot_mark_delivered():
    with pytest.raises(
        LifecycleConflictError,
        match="F10",
    ):
        validate_transition(
            fake_order(
                OrderStatus.OUT_FOR_DELIVERY,
                TRIP_ID,
            ),
            OrderStatus.DELIVERED,
            Role.DISPATCHER,
            fake_trip(),
        )


def test_dispatcher_next_status():
    assert allowed_next_status(
        fake_order(),
        Role.DISPATCHER,
    ) == OrderStatus.WAREHOUSE


def test_driver_next_status():
    assert allowed_next_status(
        fake_order(
            OrderStatus.WAREHOUSE,
            TRIP_ID,
        ),
        Role.DRIVER,
        fake_trip(),
        fake_driver(),
    ) == OrderStatus.OUT_FOR_DELIVERY


@pytest.mark.parametrize(
    "role",
    [
        Role.ADMIN,
        Role.CUSTOMER,
    ],
)
def test_read_only_roles_have_no_next_action(role):
    assert allowed_next_status(
        fake_order(),
        role,
    ) is None


def test_customer_filter_is_scoped():
    user = fake_user(Role.CUSTOMER)

    query = build_lifecycle_filter(
        user,
        order_status=OrderStatus.PLACED,
    )

    assert query["customer_id"] == USER_ID
    assert query["status"] == "placed"


def test_driver_filter_is_scoped():
    query = build_lifecycle_filter(
        fake_user(Role.DRIVER),
        driver_trip_ids=[TRIP_ID],
    )

    assert query == {
        "trip_id": {
            "$in": [TRIP_ID],
        }
    }


def test_unlinked_driver_sees_no_trip_orders():
    query = build_lifecycle_filter(
        fake_user(Role.DRIVER),
        driver_trip_ids=[],
    )

    assert query["trip_id"] == {
        "$in": [],
    }


def test_search_regex_escaped():
    query = build_lifecycle_filter(
        fake_user(Role.DISPATCHER),
        search=".*",
    )

    assert (
        query["reference_code"]["$regex"]
        == r"\.\*"
    )


def test_other_customer_cannot_view_order():
    async def run():
        order = fake_order()
        order.customer_id = OTHER_CUSTOMER_ID

        with pytest.raises(LifecycleNotFoundError):
            await authorize_order_view(
                order,
                fake_user(Role.CUSTOMER),
            )

    asyncio.run(run())


def test_unassigned_driver_cannot_view_order():
    async def run():
        order = fake_order(
            OrderStatus.WAREHOUSE,
            TRIP_ID,
        )

        other_driver = fake_driver(
            ObjectId(
                "507f1f77bcf86cd799439018"
            )
        )

        with (
            patch(
                "app.services.order_lifecycle_service."
                "Trip.get",
                new_callable=AsyncMock,
            ) as get_trip,
            patch(
                "app.services.order_lifecycle_service."
                "driver_for_user",
                new_callable=AsyncMock,
            ) as get_driver,
        ):
            get_trip.return_value = fake_trip()
            get_driver.return_value = other_driver

            with pytest.raises(LifecycleNotFoundError):
                await authorize_order_view(
                    order,
                    fake_user(Role.DRIVER),
                )

    asyncio.run(run())


def test_atomic_status_update_success():
    async def run():
        order = fake_order()

        updated_order = fake_order(
            OrderStatus.WAREHOUSE
        )

        with (
            patch(
                "app.services.order_lifecycle_service."
                "get_order_document",
                new_callable=AsyncMock,
            ) as get_order,
            patch(
                "app.services.order_lifecycle_service."
                "authorize_order_view",
                new_callable=AsyncMock,
            ) as authorize,
            patch(
                "app.services.order_lifecycle_service."
                "Order.find_one",
            ) as find_one,
            patch(
                "app.services.order_lifecycle_service."
                "Order.get",
                new_callable=AsyncMock,
            ) as refresh,
        ):
            get_order.return_value = order
            authorize.return_value = (None, None)

            find_one.return_value.update = AsyncMock(
                return_value=SimpleNamespace(
                    modified_count=1
                )
            )
            refresh.return_value = updated_order

            result = await change_order_status(
                str(ORDER_ID),
                OrderStatus.WAREHOUSE,
                fake_user(Role.DISPATCHER),
            )

        assert result.status == OrderStatus.WAREHOUSE

    asyncio.run(run())


def test_concurrent_status_change_returns_conflict():
    async def run():
        order = fake_order()

        with (
            patch(
                "app.services.order_lifecycle_service."
                "get_order_document",
                new_callable=AsyncMock,
            ) as get_order,
            patch(
                "app.services.order_lifecycle_service."
                "authorize_order_view",
                new_callable=AsyncMock,
            ) as authorize,
            patch(
                "app.services.order_lifecycle_service."
                "Order.find_one",
            ) as find_one,
        ):
            get_order.return_value = order
            authorize.return_value = (None, None)

            find_one.return_value.update = AsyncMock(
                return_value=SimpleNamespace(
                    modified_count=0
                )
            )

            with pytest.raises(LifecycleConflictError):
                await change_order_status(
                    str(ORDER_ID),
                    OrderStatus.WAREHOUSE,
                    fake_user(Role.DISPATCHER),
                )

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [
        Role.ADMIN,
        Role.DISPATCHER,
        Role.DRIVER,
        Role.CUSTOMER,
    ],
)
def test_allowed_roles_can_list_orders(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.order_lifecycle_controller."
            "list_order_lifecycle",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = (
                OrderLifecycleListResponse(
                    items=[fake_response()],
                    total=1,
                    page=1,
                    page_size=10,
                )
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    BASE_URL
                )

        assert response.status_code == 200
        assert response.json()["total"] == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [
        Role.DISPATCHER,
        Role.DRIVER,
    ],
)
def test_operational_roles_can_update(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.order_lifecycle_controller."
            "change_order_status",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = fake_response(
                status=OrderStatus.OUT_FOR_DELIVERY,
                next_status=None,
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.patch(
                    f"{BASE_URL}/{ORDER_ID}/status",
                    json={
                        "status": "out_for_delivery",
                    },
                )

        assert response.status_code == 200
        mocked.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [
        Role.ADMIN,
        Role.CUSTOMER,
    ],
)
def test_read_only_roles_cannot_update(role):
    async def run():
        app = make_app(role)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.patch(
                f"{BASE_URL}/{ORDER_ID}/status",
                json={"status": "warehouse"},
            )

        assert response.status_code == 403

    asyncio.run(run())


def test_delivered_api_request_rejected():
    async def run():
        app = make_app(Role.DISPATCHER)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.patch(
                f"{BASE_URL}/{ORDER_ID}/status",
                json={"status": "delivered"},
            )

        assert response.status_code == 422

    asyncio.run(run())


def test_missing_auth_rejected():
    async def run():
        app = make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(BASE_URL)

        assert response.status_code == 401

    asyncio.run(run())


def test_status_update_requires_csrf():
    async def run():
        app = make_app(
            Role.DISPATCHER,
            skip_csrf=False,
        )

        with patch(
            "app.controllers.order_lifecycle_controller."
            "change_order_status",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.patch(
                    f"{BASE_URL}/{ORDER_ID}/status",
                    json={"status": "warehouse"},
                )

        assert response.status_code == 403
        mocked.assert_not_awaited()

    asyncio.run(run())
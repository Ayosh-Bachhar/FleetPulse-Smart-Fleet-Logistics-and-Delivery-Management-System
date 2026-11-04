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
from app.controllers.order_intake_controller import router
from app.models.order import OrderStatus
from app.models.user import Role

from app.schemas.order_intake_schemas import (
    OrderCreate,
    OrderResponse,
    OrderListResponse,
)
from app.services.order_intake_service import (
    OrderNotFoundError,
    OrderPermissionError,
    OrderValidationError,
    build_order_filter,
    calculate_volume_m3,
    get_order,
    resolve_order_customer,
)


CUSTOMER_ID = "507f1f77bcf86cd799439011"
OTHER_ID = "507f1f77bcf86cd799439012"
ORDER_ID = "507f1f77bcf86cd799439013"

URL = "/api/v1/orders"


def order_payload():
    return {
        "pickup_address": "Uttara, Dhaka",
        "delivery_address": "Mirpur, Dhaka",
        "weight_kg": 200,
        "length_cm": 100,
        "width_cm": 50,
        "height_cm": 50,
        "is_rush": False,
    }


def fake_user(role=Role.CUSTOMER):
    return SimpleNamespace(
        id=ObjectId(CUSTOMER_ID),
        full_name="Sample Customer",
        email="customer@example.com",
        is_active=True,
        role=role,
    )


def sample_response():
    return OrderResponse(
        id=ORDER_ID,
        reference_code="FP-TEST-ORDER-001",
        customer_id=CUSTOMER_ID,
        customer_name="Sample Customer",
        customer_email="customer@example.com",
        pickup_address="Uttara, Dhaka",
        delivery_address="Mirpur, Dhaka",
        weight_kg=200,
        length_cm=100,
        width_cm=50,
        height_cm=50,
        volume_m3=0.25,
        is_rush=False,
        status=OrderStatus.PLACED,
        trip_id=None,
        public_tracking_uuid=(
            "b8a3730e-a91d-4f22-b275-bc0a54eab91f"
        ),
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


def make_app(role=None, bypass_csrf=True):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    if role is not None:
        app.dependency_overrides[get_current_user] = (
            lambda: fake_user(role)
        )

    if bypass_csrf:
        app.dependency_overrides[require_csrf] = (
            lambda: None
        )

    return app


def test_package_volume_calculation():
    assert calculate_volume_m3(
        100, 50, 50
    ) == 0.25

    assert calculate_volume_m3(
        120, 80, 70
    ) == 0.672

    assert calculate_volume_m3(
        1, 1, 1
    ) == 0.000001


def test_invalid_volume_dimensions():
    with pytest.raises(OrderValidationError):
        calculate_volume_m3(
            0, 50, 50
        )


def test_valid_order_schema():
    data = OrderCreate(**order_payload())

    assert data.weight_kg == 200
    assert data.is_rush is False


def test_address_whitespace_is_trimmed():
    payload = order_payload()

    payload["pickup_address"] = (
        "   Uttara,   Dhaka   "
    )

    data = OrderCreate(**payload)

    assert data.pickup_address == "Uttara, Dhaka"


def test_matching_addresses_rejected():
    payload = order_payload()

    payload["delivery_address"] = (
        "uttara, dhaka"
    )

    with pytest.raises(ValidationError):
        OrderCreate(**payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("weight_kg", 0),
        ("weight_kg", -10),
        ("length_cm", 0),
        ("width_cm", -1),
        ("height_cm", 0),
        ("pickup_address", "A"),
        ("delivery_address", ""),
    ],
)
def test_invalid_order_fields(field, value):
    payload = order_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        OrderCreate(**payload)


@pytest.mark.parametrize(
    "protected_field,value",
    [
        ("status", "warehouse"),
        ("customer_id", CUSTOMER_ID),
        ("trip_id", ORDER_ID),
        ("volume_m3", 50),
    ],
)
def test_customer_cannot_supply_server_fields(
    protected_field,
    value,
):
    payload = order_payload()
    payload[protected_field] = value

    with pytest.raises(ValidationError):
        OrderCreate(**payload)


def test_customer_query_is_always_scoped():
    user = fake_user(Role.CUSTOMER)

    result = build_order_filter(
        user,
        order_status=OrderStatus.PLACED,
        search="Uttara",
    )

    assert result["customer_id"] == user.id
    assert result["status"] == "placed"
    assert "$or" in result


def test_dispatcher_query_is_global():
    user = fake_user(Role.DISPATCHER)

    result = build_order_filter(
        user,
        search="FP-TEST",
    )

    assert "customer_id" not in result
    assert "$or" in result


def test_search_input_is_regex_escaped():
    result = build_order_filter(
        fake_user(),
        search=".*",
    )

    assert (
        result["$or"][0]["reference_code"]["$regex"]
        == r"\.\*"
    )


def test_customer_cannot_create_for_another():
    async def run():
        data = OrderCreate(
            **order_payload(),
            customer_email="another@example.com",
        )

        with pytest.raises(OrderPermissionError):
            await resolve_order_customer(
                data,
                fake_user(Role.CUSTOMER),
            )

    asyncio.run(run())


def test_customer_uses_own_identity():
    async def run():
        customer = fake_user()

        result = await resolve_order_customer(
            OrderCreate(**order_payload()),
            customer,
        )

        assert result.id == customer.id

    asyncio.run(run())


def test_dispatcher_requires_customer_email():
    async def run():
        with pytest.raises(OrderValidationError):
            await resolve_order_customer(
                OrderCreate(**order_payload()),
                fake_user(Role.DISPATCHER),
            )

    asyncio.run(run())


def test_dispatcher_can_select_customer():
    async def run():
        data = OrderCreate(
            **order_payload(),
            customer_email="CUSTOMER@example.com",
        )

        with patch(
            "app.services.order_intake_service."
            "User.find_one",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = fake_user()

            customer = await resolve_order_customer(
                data,
                fake_user(Role.DISPATCHER),
            )

        assert customer.role == Role.CUSTOMER
        assert customer.id == ObjectId(CUSTOMER_ID)

    asyncio.run(run())


def test_dispatcher_rejects_noncustomer_account():
    async def run():
        data = OrderCreate(
            **order_payload(),
            customer_email="driver@example.com",
        )

        with patch(
            "app.services.order_intake_service."
            "User.find_one",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = fake_user(Role.DRIVER)

            with pytest.raises(OrderValidationError):
                await resolve_order_customer(
                    data,
                    fake_user(Role.DISPATCHER),
                )

    asyncio.run(run())


def test_customer_cannot_read_other_order():
    async def run():
        other_order = SimpleNamespace(
            customer_id=ObjectId(OTHER_ID)
        )

        with patch(
            "app.services.order_intake_service."
            "Order.get",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = other_order

            with pytest.raises(OrderNotFoundError):
                await get_order(
                    ORDER_ID,
                    fake_user(),
                )

    asyncio.run(run())


def test_invalid_order_id_rejected():
    async def run():
        with pytest.raises(OrderNotFoundError):
            await get_order(
                "not-an-object-id",
                fake_user(),
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DISPATCHER],
)
def test_allowed_roles_can_list_orders(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.order_intake_controller."
            "list_orders",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = OrderListResponse(
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

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DISPATCHER],
)
def test_allowed_roles_can_create_orders(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.order_intake_controller."
            "create_order",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            payload = order_payload()

            if role == Role.DISPATCHER:
                payload["customer_email"] = (
                    "customer@example.com"
                )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=payload,
                )

        assert response.status_code == 201
        assert response.json()["status"] == "placed"
        mocked.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DRIVER],
)
def test_other_roles_cannot_use_order_intake(role):
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


def test_order_creation_requires_csrf():
    async def run():
        app = make_app(
            Role.CUSTOMER,
            bypass_csrf=False,
        )

        with patch(
            "app.controllers.order_intake_controller."
            "create_order",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=order_payload(),
                )

        assert response.status_code == 403
        mocked.assert_not_awaited()

    asyncio.run(run())
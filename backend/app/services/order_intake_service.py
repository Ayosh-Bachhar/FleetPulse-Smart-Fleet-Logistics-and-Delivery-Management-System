import re
from datetime import datetime, timezone
from decimal import Decimal

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.order import Order, OrderStatus
from app.models.user import User, Role

from app.schemas.order_intake_schemas import (
    OrderCreate,
    OrderResponse,
    OrderListResponse,
)


class OrderNotFoundError(Exception):
    pass


class OrderValidationError(Exception):
    pass


class OrderPermissionError(Exception):
    pass


class OrderConflictError(Exception):
    pass


def calculate_volume_m3(
    length_cm,
    width_cm,
    height_cm,
):
    """
    Convert cubic centimetres into cubic metres.

    Input: centimetres.
    Output: cubic metres rounded to 6 decimals.
    """
    dimensions = [
        Decimal(str(length_cm)),
        Decimal(str(width_cm)),
        Decimal(str(height_cm)),
    ]

    if any(value < 1 for value in dimensions):
        raise OrderValidationError(
            "Every package dimension must be "
            "at least 1 cm."
        )

    volume = (
        dimensions[0]
        * dimensions[1]
        * dimensions[2]
        / Decimal("1000000")
    )

    return float(
        round(volume, 6)
    )


def build_order_filter(
    current_user,
    order_status=None,
    search=None,
):
    """
    Customers are always restricted to their
    own records, including when searching.
    """
    filters = {}

    if current_user.role == Role.CUSTOMER:
        filters["customer_id"] = current_user.id

    elif current_user.role != Role.DISPATCHER:
        raise OrderPermissionError(
            "You cannot view order intake records."
        )

    if order_status is not None:
        filters["status"] = order_status.value

    if search:
        safe_search = re.escape(
            search.strip()
        )

        if safe_search:
            filters["$or"] = [
                {
                    "reference_code": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
                {
                    "pickup_address": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
                {
                    "delivery_address": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
            ]

    return filters


async def resolve_order_customer(
    data: OrderCreate,
    current_user: User,
):
    if current_user.role == Role.CUSTOMER:
        if data.customer_email is not None:
            raise OrderPermissionError(
                "Customers cannot place orders "
                "on another account's behalf."
            )

        return current_user

    if current_user.role != Role.DISPATCHER:
        raise OrderPermissionError(
            "You cannot create orders."
        )

    if data.customer_email is None:
        raise OrderValidationError(
            "Enter the registered customer's email."
        )

    customer = await User.find_one(
        {"email": str(data.customer_email)}
    )

    if (
        customer is None
        or customer.role != Role.CUSTOMER
        or not customer.is_active
    ):
        raise OrderValidationError(
            "A registered, active Customer account "
            "with this email was not found."
        )

    return customer


async def order_to_response(
    order: Order,
    customer: User | None = None,
):
    if customer is None:
        customer = await User.get(
            order.customer_id
        )

    if customer is None:
        raise OrderNotFoundError(
            "The customer account linked to "
            "this order no longer exists."
        )

    return OrderResponse(
        id=str(order.id),
        reference_code=order.reference_code,
        customer_id=str(order.customer_id),
        customer_name=customer.full_name,
        customer_email=customer.email,
        pickup_address=order.pickup_address,
        delivery_address=order.delivery_address,
        weight_kg=order.weight_kg,
        length_cm=order.length_cm,
        width_cm=order.width_cm,
        height_cm=order.height_cm,
        volume_m3=order.volume_m3,
        is_rush=order.is_rush,
        status=order.status,
        trip_id=(
            str(order.trip_id)
            if order.trip_id is not None
            else None
        ),
        public_tracking_uuid=order.public_tracking_uuid,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def create_order(
    data: OrderCreate,
    current_user: User,
):
    customer = await resolve_order_customer(
        data,
        current_user,
    )

    volume_m3 = calculate_volume_m3(
        data.length_cm,
        data.width_cm,
        data.height_cm,
    )

    new_order = Order(
        customer_id=customer.id,
        pickup_address=data.pickup_address,
        delivery_address=data.delivery_address,
        weight_kg=data.weight_kg,
        length_cm=data.length_cm,
        width_cm=data.width_cm,
        height_cm=data.height_cm,
        volume_m3=volume_m3,
        is_rush=data.is_rush,
        status=OrderStatus.PLACED,
        trip_id=None,
        created_at=datetime.now(timezone.utc),
    )

    try:
        await new_order.insert()

    except DuplicateKeyError as exc:
        raise OrderConflictError(
            "A unique order identifier conflicted. "
            "Please try placing the order again."
        ) from exc

    return await order_to_response(
        new_order,
        customer,
    )


async def list_orders(
    current_user: User,
    order_status=None,
    search=None,
    page=1,
    page_size=10,
):
    filters = build_order_filter(
        current_user,
        order_status=order_status,
        search=search,
    )

    query = Order.find(filters)
    total = await query.count()

    orders = await (
        query.sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    responses = []

    for order in orders:
        responses.append(
            await order_to_response(order)
        )

    return OrderListResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_order(
    order_id: str,
    current_user: User,
):
    if current_user.role not in (
        Role.CUSTOMER,
        Role.DISPATCHER,
    ):
        raise OrderPermissionError(
            "You cannot view order intake records."
        )

    if not ObjectId.is_valid(order_id):
        raise OrderNotFoundError(
            "Order not found."
        )

    order = await Order.get(
        ObjectId(order_id)
    )

    if order is None:
        raise OrderNotFoundError(
            "Order not found."
        )

    # Return 404 rather than revealing whether
    # somebody else's order exists.
    if (
        current_user.role == Role.CUSTOMER
        and order.customer_id != current_user.id
    ):
        raise OrderNotFoundError(
            "Order not found."
        )

    return await order_to_response(order)
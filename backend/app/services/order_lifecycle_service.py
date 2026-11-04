import re
from datetime import datetime, timezone

from bson import ObjectId

from app.models.driver import Driver
from app.models.order import Order, OrderStatus
from app.models.trip import Trip, TripStatus
from app.models.user import Role

from app.schemas.order_lifecycle_schemas import (
    OrderLifecycleResponse,
    OrderLifecycleListResponse,
)


class LifecycleNotFoundError(Exception):
    pass


class LifecyclePermissionError(Exception):
    pass


class LifecycleConflictError(Exception):
    pass


def validate_transition(
    order,
    target_status,
    role,
    trip=None,
    driver=None,
):
    """
    F9 transition rules.

    Placed -> Warehouse:
        Dispatcher only, before dispatch.

    Warehouse -> Out for Delivery:
        Dispatcher or assigned Driver,
        after F11 dispatch.

    Out for Delivery -> Delivered:
        Reserved for F10 delivery proof.
    """
    if target_status == OrderStatus.WAREHOUSE:
        if role != Role.DISPATCHER:
            raise LifecyclePermissionError(
                "Only Dispatchers can prepare orders."
            )

        if order.status != OrderStatus.PLACED:
            raise LifecycleConflictError(
                "Only Placed orders can move to Warehouse."
            )

        if order.trip_id is not None:
            raise LifecycleConflictError(
                "A Placed order cannot already "
                "be assigned to a trip."
            )

        return

    if target_status == OrderStatus.OUT_FOR_DELIVERY:
        if role not in (
            Role.DISPATCHER,
            Role.DRIVER,
        ):
            raise LifecyclePermissionError(
                "You cannot start delivery."
            )

        if order.status != OrderStatus.WAREHOUSE:
            raise LifecycleConflictError(
                "Only Warehouse orders can move "
                "to Out for Delivery."
            )

        if (
            order.trip_id is None
            or trip is None
            or trip.id != order.trip_id
            or trip.status != TripStatus.DISPATCHED
            or order.id not in trip.order_ids
        ):
            raise LifecycleConflictError(
                "Dispatch this order through F11 "
                "before starting delivery."
            )

        if role == Role.DRIVER:
            if (
                driver is None
                or driver.id != trip.driver_id
            ):
                raise LifecyclePermissionError(
                    "Only the assigned Driver can "
                    "start this delivery."
                )

        return

    if target_status == OrderStatus.DELIVERED:
        raise LifecycleConflictError(
            "Delivered status requires F10 "
            "Delivery Proof."
        )

    raise LifecycleConflictError(
        "Invalid or unsupported status transition."
    )


def build_lifecycle_filter(
    current_user,
    driver_trip_ids=None,
    order_status=None,
    search=None,
):
    filters = {}

    if current_user.role == Role.CUSTOMER:
        filters["customer_id"] = current_user.id

    elif current_user.role == Role.DRIVER:
        filters["trip_id"] = {
            "$in": driver_trip_ids or [],
        }

    elif current_user.role not in (
        Role.ADMIN,
        Role.DISPATCHER,
    ):
        raise LifecyclePermissionError(
            "You cannot view order lifecycle records."
        )

    if order_status is not None:
        filters["status"] = order_status.value

    if search:
        safe_search = re.escape(
            search.strip()
        )

        if safe_search:
            filters["reference_code"] = {
                "$regex": safe_search,
                "$options": "i",
            }

    return filters


async def driver_for_user(current_user):
    return await Driver.find_one({
        "user_id": current_user.id,
    })


async def assigned_trip_ids(driver):
    if driver is None:
        return []

    trips = await Trip.find({
        "driver_id": driver.id,
    }).to_list()

    return [trip.id for trip in trips]


async def get_order_document(order_id):
    if not ObjectId.is_valid(order_id):
        raise LifecycleNotFoundError(
            "Order not found."
        )

    order = await Order.get(ObjectId(order_id))

    if order is None:
        raise LifecycleNotFoundError(
            "Order not found."
        )

    return order


async def authorize_order_view(
    order,
    current_user,
):
    """
    Returns the linked Driver and Trip when present.

    Unauthorized customers and drivers receive 404
    so other people's order identifiers aren't exposed.
    """
    driver = None
    trip = None

    if order.trip_id is not None:
        trip = await Trip.get(order.trip_id)

    if current_user.role == Role.CUSTOMER:
        if order.customer_id != current_user.id:
            raise LifecycleNotFoundError(
                "Order not found."
            )

    elif current_user.role == Role.DRIVER:
        driver = await driver_for_user(current_user)

        if (
            driver is None
            or trip is None
            or trip.driver_id != driver.id
            or order.id not in trip.order_ids
        ):
            raise LifecycleNotFoundError(
                "Order not found."
            )

    elif current_user.role not in (
        Role.ADMIN,
        Role.DISPATCHER,
    ):
        raise LifecyclePermissionError(
            "You cannot view this order."
        )

    return driver, trip


def allowed_next_status(
    order,
    role,
    trip=None,
    driver=None,
):
    """
    Exposes only a valid action for the current user.
    Customers and Admins are read-only.
    """
    if role not in (
        Role.DISPATCHER,
        Role.DRIVER,
    ):
        return None

    candidates = (
        OrderStatus.WAREHOUSE,
        OrderStatus.OUT_FOR_DELIVERY,
    )

    for candidate in candidates:
        try:
            validate_transition(
                order,
                candidate,
                role,
                trip,
                driver,
            )

        except (
            LifecyclePermissionError,
            LifecycleConflictError,
        ):
            continue

        return candidate

    return None


async def order_to_lifecycle_response(
    order,
    current_user,
    driver=None,
    trip=None,
):
    if (
        trip is None
        and order.trip_id is not None
        and current_user.role in (
            Role.DISPATCHER,
            Role.DRIVER,
        )
    ):
        trip = await Trip.get(order.trip_id)

    return OrderLifecycleResponse(
        id=str(order.id),
        reference_code=order.reference_code,
        pickup_address=order.pickup_address,
        delivery_address=order.delivery_address,
        status=order.status,
        trip_id=(
            str(order.trip_id)
            if order.trip_id is not None
            else None
        ),
        is_rush=order.is_rush,
        created_at=order.created_at,
        updated_at=order.updated_at,
        allowed_next_status=allowed_next_status(
            order,
            current_user.role,
            trip,
            driver,
        ),
    )


async def list_order_lifecycle(
    current_user,
    order_status=None,
    search=None,
    page=1,
    page_size=10,
):
    driver = None
    trip_ids = None

    if current_user.role == Role.DRIVER:
        driver = await driver_for_user(
            current_user
        )
        trip_ids = await assigned_trip_ids(driver)

    filters = build_lifecycle_filter(
        current_user,
        driver_trip_ids=trip_ids,
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

    items = []

    for order in orders:
        items.append(
            await order_to_lifecycle_response(
                order,
                current_user,
                driver=driver,
            )
        )

    return OrderLifecycleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_order_lifecycle(
    order_id,
    current_user,
):
    order = await get_order_document(order_id)

    driver, trip = await authorize_order_view(
        order,
        current_user,
    )

    return await order_to_lifecycle_response(
        order,
        current_user,
        driver=driver,
        trip=trip,
    )


async def change_order_status(
    order_id,
    target_status,
    current_user,
):
    if current_user.role not in (
        Role.DISPATCHER,
        Role.DRIVER,
    ):
        raise LifecyclePermissionError(
            "Only Dispatchers and assigned Drivers "
            "may change delivery status."
        )

    order = await get_order_document(order_id)

    driver, trip = await authorize_order_view(
        order,
        current_user,
    )

    validate_transition(
        order,
        target_status,
        current_user.role,
        trip,
        driver,
    )

    now = datetime.now(timezone.utc)

    # Atomic conditional update.
    # Only change the status if it still matches
    # the value we validated above.
    #
    # Also verify the trip assignment was not
    # changed or cancelled since our read.
    result = await Order.find_one({
        "_id": order.id,
        "status": order.status.value,
        "trip_id": order.trip_id,
    }).update({
        "$set": {
            "status": target_status.value,
            "updated_at": now,
        }
    })

    if (
        result is None
        or result.modified_count != 1
    ):
        raise LifecycleConflictError(
            "Order was changed by another request. "
            "Reload the page and try again."
        )

    updated_order = await Order.get(
        order.id
    )

    return await order_to_lifecycle_response(
        updated_order,
        current_user,
        driver=driver,
        trip=trip,
    )
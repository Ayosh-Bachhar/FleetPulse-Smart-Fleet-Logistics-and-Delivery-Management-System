from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import isclose

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.connection import client

from app.models.order import Order, OrderStatus
from app.models.trip import Trip, TripStatus
from app.models.shift import Shift, ShiftStatus
from app.models.driver import Driver, DriverStatus
from app.models.vehicle import (
    Vehicle,
    is_vehicle_dispatchable,
)
from app.models.user import User, Role

from app.schemas.dispatch_planning_schemas import (
    DispatchOrderResponse,
    DispatchOrderListResponse,
    TripResponse,
    TripListResponse,
)

from app.services.driver_management_service import (
    is_license_compatible,
)


BD_TIMEZONE = timezone(timedelta(hours=6))


class DispatchNotFoundError(Exception):
    pass


class DispatchValidationError(Exception):
    pass


class DispatchConflictError(Exception):
    pass


def to_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def periods_overlap(start_a, end_a, start_b, end_b):
    return (
        to_utc(start_a) < to_utc(end_b)
        and to_utc(end_a) > to_utc(start_b)
    )


def check_dispatch_resources(driver, vehicle, shift):
    if shift.status != ShiftStatus.SCHEDULED:
        raise DispatchValidationError(
            "Only scheduled shifts can be dispatched."
        )

    if shift.driver_id != driver.id:
        raise DispatchValidationError(
            "The driver does not match the selected shift."
        )

    if shift.vehicle_id != vehicle.id:
        raise DispatchValidationError(
            "The vehicle does not match the selected shift."
        )

    start_at = to_utc(shift.start_at)
    end_at = to_utc(shift.end_at)

    if end_at <= start_at:
        raise DispatchValidationError(
            "Invalid shift time range."
        )

    if end_at <= datetime.now(timezone.utc):
        raise DispatchValidationError(
            "Cannot dispatch an expired shift."
        )

    if driver.status != DriverStatus.AVAILABLE:
        raise DispatchValidationError(
            "Driver is not available."
        )

    if not is_vehicle_dispatchable(vehicle):
        raise DispatchValidationError(
            "Vehicle is unavailable or requires maintenance."
        )

    if not is_license_compatible(
        driver.license_class,
        vehicle.vehicle_type,
    ):
        raise DispatchValidationError(
            "Driver license class does not permit "
            "this vehicle type."
        )

    # End time is exclusive.
    last_day = (
        end_at - timedelta(microseconds=1)
    ).astimezone(BD_TIMEZONE).date()

    if driver.license_expiry < last_day:
        raise DispatchValidationError(
            "Driver license expires before the shift ends."
        )

    return start_at, end_at


def validate_dispatch_orders(orders):
    if not orders:
        raise DispatchValidationError(
            "Select at least one order."
        )

    for order in orders:
        if order.status != OrderStatus.WAREHOUSE:
            raise DispatchValidationError(
                f"Order {order.reference_code} "
                "must be in Warehouse status."
            )

        if order.trip_id is not None:
            raise DispatchConflictError(
                f"Order {order.reference_code} "
                "is already assigned to a trip."
            )

        if order.weight_kg <= 0 or order.volume_m3 <= 0:
            raise DispatchValidationError(
                "Order weight and volume must be positive."
            )

        calculated_volume = (
            order.length_cm
            * order.width_cm
            * order.height_cm
            / 1_000_000
        )

        if not isclose(
            calculated_volume,
            order.volume_m3,
            rel_tol=0.00001,
            abs_tol=0.000001,
        ):
            raise DispatchValidationError(
                f"Order {order.reference_code} "
                "has inconsistent dimensions and volume."
            )


def calculate_dispatch_load(orders, vehicle):
    validate_dispatch_orders(orders)

    if vehicle.volume_capacity_m3 is None:
        raise DispatchValidationError(
            "This vehicle has no volume capacity configured. "
            "Update it through Fleet Management first."
        )

    weight = sum(
        (
            Decimal(str(order.weight_kg))
            for order in orders
        ),
        Decimal("0"),
    )

    volume = sum(
        (
            Decimal(str(order.volume_m3))
            for order in orders
        ),
        Decimal("0"),
    )

    if weight > Decimal(str(vehicle.capacity_kg)):
        raise DispatchValidationError(
            "Total order weight exceeds vehicle capacity."
        )

    if volume > Decimal(str(vehicle.volume_capacity_m3)):
        raise DispatchValidationError(
            "Total order volume exceeds vehicle capacity."
        )

    return (
        round(float(weight), 3),
        round(float(volume), 6),
    )


def order_to_response(order):
    return DispatchOrderResponse(
        id=str(order.id),
        reference_code=order.reference_code,
        weight_kg=order.weight_kg,
        volume_m3=order.volume_m3,
        pickup_address=order.pickup_address,
        delivery_address=order.delivery_address,
        is_rush=order.is_rush,
        status=order.status,
    )


async def list_ready_orders(
    page=1,
    page_size=100,
):
    query = Order.find({
        "status": OrderStatus.WAREHOUSE.value,
        "trip_id": None,
    })

    total = await query.count()

    orders = await (
        query.sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    return DispatchOrderListResponse(
        items=[
            order_to_response(order)
            for order in orders
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def trip_to_response(trip):
    driver = await Driver.get(trip.driver_id)
    vehicle = await Vehicle.get(trip.vehicle_id)

    order_references = []

    for order_id in trip.order_ids:
        order = await Order.get(order_id)

        order_references.append(
            order.reference_code
            if order is not None
            else str(order_id)
        )

    return TripResponse(
        id=str(trip.id),
        order_ids=[
            str(value)
            for value in trip.order_ids
        ],
        order_count=len(trip.order_ids),
        order_references=order_references,
        driver_id=str(trip.driver_id),
        driver_name=(
            driver.full_name
            if driver is not None
            else "Unknown driver"
        ),
        vehicle_id=str(trip.vehicle_id),
        vehicle_registration=(
            vehicle.registration_number
            if vehicle is not None
            else "Unknown vehicle"
        ),
        vehicle_type=(
            vehicle.vehicle_type
            if vehicle is not None
            else "Unknown"
        ),
        shift_id=str(trip.shift_id),
        start_at=to_utc(trip.start_at),
        end_at=to_utc(trip.end_at),
        total_weight_kg=trip.total_weight_kg,
        total_volume_m3=trip.total_volume_m3,
        status=trip.status,
        estimated_distance_km=trip.estimated_distance_km,
        actual_distance_km=trip.actual_distance_km,
        created_by=str(trip.created_by),
        created_at=to_utc(trip.created_at),
        updated_at=(
            to_utc(trip.updated_at)
            if trip.updated_at is not None
            else None
        ),
        completed_at=(
            to_utc(trip.completed_at)
            if trip.completed_at is not None
            else None
        ),
        cancelled_at=(
            to_utc(trip.cancelled_at)
            if trip.cancelled_at is not None
            else None
        ),
    )


async def get_trip_document(
    trip_id,
    session=None,
):
    if not ObjectId.is_valid(trip_id):
        raise DispatchNotFoundError(
            "Trip not found."
        )

    trip = await Trip.get(
        ObjectId(trip_id),
        session=session,
    )

    if trip is None:
        raise DispatchNotFoundError(
            "Trip not found."
        )

    return trip


async def list_trips(
    trip_status=None,
    page=1,
    page_size=10,
):
    filters = []

    if trip_status is not None:
        filters.append({
            "status": trip_status.value
        })

    query = Trip.find(*filters)

    total = await query.count()

    trips = await (
        query.sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    return TripListResponse(
        items=[
            await trip_to_response(trip)
            for trip in trips
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_trip(trip_id):
    trip = await get_trip_document(trip_id)

    return await trip_to_response(trip)


async def ensure_driver_account_active(
    driver,
    session,
):
    if driver.user_id is None:
        return

    user = await User.get(
        driver.user_id,
        session=session,
    )

    if (
        user is None
        or not user.is_active
        or user.role != Role.DRIVER
    ):
        raise DispatchValidationError(
            "Linked Driver account is inactive or invalid."
        )


async def dispatch_trip(
    data,
    current_user_id,
):
    shift_id = ObjectId(data.shift_id)

    requested_order_ids = [
        ObjectId(value)
        for value in data.order_ids
    ]

    created_trip = None

    try:
        # PyMongo AsyncMongoClient.start_session()
        # returns a session directly. Do not await it.
        async with client.start_session() as session:

            # AsyncClientSession.start_transaction()
            # is a coroutine and must be awaited.
            async with await session.start_transaction():

                shift = await Shift.get(
                    shift_id,
                    session=session,
                )

                if shift is None:
                    raise DispatchNotFoundError(
                        "Selected shift does not exist."
                    )

                driver = await Driver.get(
                    shift.driver_id,
                    session=session,
                )

                vehicle = await Vehicle.get(
                    shift.vehicle_id,
                    session=session,
                )

                if driver is None or vehicle is None:
                    raise DispatchValidationError(
                        "Shift has a missing driver or vehicle."
                    )

                start_at, end_at = check_dispatch_resources(
                    driver,
                    vehicle,
                    shift,
                )

                await ensure_driver_account_active(
                    driver,
                    session,
                )

                # Check whether another dispatched trip
                # already occupies this driver or vehicle
                # during the selected shift.
                existing_trip = await Trip.find(
                    {
                        "status": TripStatus.DISPATCHED.value,
                        "start_at": {"$lt": end_at},
                        "end_at": {"$gt": start_at},
                        "$or": [
                            {"driver_id": driver.id},
                            {"vehicle_id": vehicle.id},
                        ],
                    },
                    session=session,
                ).first_or_none()

                if existing_trip is not None:
                    raise DispatchConflictError(
                        "The driver or vehicle already has an "
                        "overlapping dispatched trip."
                    )

                orders = []

                for order_id in requested_order_ids:
                    order = await Order.get(
                        order_id,
                        session=session,
                    )

                    if order is None:
                        raise DispatchNotFoundError(
                            "One of the selected orders "
                            "does not exist."
                        )

                    orders.append(order)

                # Validate order status, assignment,
                # weight, volume and vehicle capacity.
                total_weight, total_volume = (
                    calculate_dispatch_load(
                        orders,
                        vehicle,
                    )
                )

                now = datetime.now(timezone.utc)

                created_trip = Trip(
                    order_ids=requested_order_ids,
                    driver_id=driver.id,
                    vehicle_id=vehicle.id,
                    shift_id=shift.id,
                    start_at=start_at,
                    end_at=end_at,
                    total_weight_kg=total_weight,
                    total_volume_m3=total_volume,
                    status=TripStatus.DISPATCHED,
                    created_by=ObjectId(
                        current_user_id
                    ),
                )

                # All changes belong to the same
                # MongoDB transaction.
                await created_trip.insert(
                    session=session,
                )

                for order in orders:
                    order.trip_id = created_trip.id
                    order.updated_at = now

                    # F9 owns order lifecycle transitions.
                    # Warehouse status remains unchanged.
                    await order.save(
                        session=session,
                    )

                # Update the resources inside the
                # transaction to detect concurrent
                # conflicting dispatch attempts.
                await driver.set(
                    {"updated_at": now},
                    session=session,
                )

                await vehicle.set(
                    {"updated_at": now},
                    session=session,
                )

        # Transaction committed successfully.
        return await trip_to_response(
            created_trip
        )

    except DuplicateKeyError as exc:
        raise DispatchConflictError(
            "One or more selected orders have already "
            "been assigned to another active trip. "
            "Reload the page and try again."
        ) from exc

    except PyMongoError as exc:
        if exc.has_error_label(
            "TransientTransactionError"
        ):
            raise DispatchConflictError(
                "Concurrent dispatch conflict. "
                "Reload the page and try again."
            ) from exc

        raise


async def complete_trip(
    trip_id,
    actual_distance_km=None,
):
    trip = None

    try:
        async with client.start_session() as session:
            async with await session.start_transaction():

                trip = await get_trip_document(
                    trip_id,
                    session=session,
                )

                if trip.status != TripStatus.DISPATCHED:
                    raise DispatchConflictError(
                        "Only dispatched trips can be completed."
                    )

                now = datetime.now(timezone.utc)

                trip.status = TripStatus.COMPLETED
                trip.completed_at = now
                trip.updated_at = now

                if actual_distance_km is not None:
                    trip.actual_distance_km = (
                        actual_distance_km
                    )

                await trip.save(
                    session=session,
                )

        return await trip_to_response(trip)

    except PyMongoError as exc:
        if exc.has_error_label(
            "TransientTransactionError"
        ):
            raise DispatchConflictError(
                "Trip was modified concurrently. "
                "Reload and try again."
            ) from exc

        raise


async def cancel_trip(trip_id):
    trip = None

    try:
        async with client.start_session() as session:
            async with await session.start_transaction():

                trip = await get_trip_document(
                    trip_id,
                    session=session,
                )

                if trip.status != TripStatus.DISPATCHED:
                    raise DispatchConflictError(
                        "Only dispatched trips can be cancelled."
                    )

                orders = []

                for order_id in trip.order_ids:
                    order = await Order.get(
                        order_id,
                        session=session,
                    )

                    if (
                        order is None
                        or order.trip_id != trip.id
                        or order.status != OrderStatus.WAREHOUSE
                    ):
                        raise DispatchConflictError(
                            "Cannot cancel a trip after an "
                            "order has progressed beyond "
                            "Warehouse."
                        )

                    orders.append(order)

                now = datetime.now(timezone.utc)

                # Release all assigned warehouse orders.
                for order in orders:
                    order.trip_id = None
                    order.updated_at = now

                    await order.save(
                        session=session,
                    )

                trip.status = TripStatus.CANCELLED
                trip.cancelled_at = now
                trip.updated_at = now

                await trip.save(
                    session=session,
                )

        return await trip_to_response(trip)

    except PyMongoError as exc:
        if exc.has_error_label(
            "TransientTransactionError"
        ):
            raise DispatchConflictError(
                "Trip was modified concurrently. "
                "Reload and try again."
            ) from exc

        raise
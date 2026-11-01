import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.database.connection import client
from app.integrations.geoapify_routing_client import (
    GeoapifyRouteError,
    calculate_geoapify_route,
    haversine_m,
)
from app.models.order import Order
from app.models.trip import Trip, TripStatus
from app.models.trip_route import TripRoute
from app.models.vehicle import Vehicle
from app.schemas.route_distance_and_time_schemas import (
    RouteStopResponse,
)
from app.schemas.stop_sequencing_schemas import (
    SequenceVariantResponse,
    StopSequenceResponse,
)


class SequenceNotFoundError(Exception):
    pass


class SequenceValidationError(Exception):
    pass


class SequenceConflictError(Exception):
    pass


class SequenceUnavailableError(Exception):
    pass


def stop_key(stop):
    return str(stop.order_id), stop.kind


def straight_line_distance_m(stops):
    return sum(
        haversine_m(
            first.latitude,
            first.longitude,
            second.latitude,
            second.longitude,
        )
        for first, second in zip(stops, stops[1:])
    )


def validate_sequence(stops, orders, vehicle):
    """
    Every order requires one pickup and one delivery.
    Deliveries must follow pickups.
    Cargo must remain within both capacities.
    """
    order_map = {
        str(order.id): order
        for order in orders
    }

    if not orders or len(order_map) != len(orders):
        raise SequenceValidationError(
            "Invalid trip orders."
        )

    expected = {
        (str(order.id), kind)
        for order in orders
        for kind in ("pickup", "delivery")
    }

    actual = [stop_key(stop) for stop in stops]

    if (
        len(actual) != len(expected)
        or set(actual) != expected
    ):
        raise SequenceValidationError(
            "Exactly one pickup and one delivery "
            "are required for every order."
        )

    capacity_kg = vehicle.capacity_kg
    capacity_m3 = vehicle.volume_capacity_m3

    if capacity_m3 is None:
        raise SequenceValidationError(
            "Vehicle volume capacity is not configured."
        )

    if not all(
        isfinite(float(value)) and float(value) > 0
        for value in (capacity_kg, capacity_m3)
    ):
        raise SequenceValidationError(
            "Vehicle capacity must be positive."
        )

    picked_up = set()
    delivered = set()

    current_weight = 0.0
    current_volume = 0.0
    epsilon = 1e-6

    for stop in stops:
        order_id, kind = stop_key(stop)
        order = order_map[order_id]

        if kind == "pickup":
            if order_id in picked_up:
                raise SequenceValidationError(
                    "Duplicate pickup."
                )

            picked_up.add(order_id)
            current_weight += order.weight_kg
            current_volume += order.volume_m3

        else:
            if (
                order_id not in picked_up
                or order_id in delivered
            ):
                raise SequenceValidationError(
                    "Delivery must follow its pickup."
                )

            delivered.add(order_id)
            current_weight -= order.weight_kg
            current_volume -= order.volume_m3

        if (
            current_weight > capacity_kg + epsilon
            or current_volume > capacity_m3 + epsilon
            or current_weight < -epsilon
            or current_volume < -epsilon
        ):
            raise SequenceValidationError(
                "Stop sequence exceeds vehicle capacity."
            )

    if len(delivered) != len(orders):
        raise SequenceValidationError(
            "All orders must be delivered."
        )


def nearest_neighbour_sequence(stops, orders, vehicle):
    """
    Select the nearest feasible next stop.

    - Keep the first pickup fixed.
    - Deliver only previously picked-up orders.
    - Never exceed vehicle capacity.
    - Break equal-distance ties by original order.

    This is a greedy algorithm, not guaranteed
    to find the global optimum.
    """
    validate_sequence(stops, orders, vehicle)

    if stops[0].kind != "pickup":
        raise SequenceValidationError(
            "The first stop must be a pickup."
        )

    order_map = {
        str(order.id): order
        for order in orders
    }

    result = [stops[0]]
    remaining = list(enumerate(stops[1:], start=1))

    first_order = order_map[
        str(stops[0].order_id)
    ]

    picked_up = {str(first_order.id)}

    weight = first_order.weight_kg
    volume = first_order.volume_m3
    epsilon = 1e-6

    while remaining:
        current = result[-1]
        candidates = []

        for index, stop in remaining:
            order_id, kind = stop_key(stop)
            order = order_map[order_id]

            if kind == "delivery":
                if order_id not in picked_up:
                    continue

            elif (
                weight + order.weight_kg
                > vehicle.capacity_kg + epsilon
                or volume + order.volume_m3
                > vehicle.volume_capacity_m3 + epsilon
            ):
                continue

            distance = haversine_m(
                current.latitude,
                current.longitude,
                stop.latitude,
                stop.longitude,
            )

            candidates.append(
                (distance, index, stop)
            )

        if not candidates:
            raise SequenceValidationError(
                "No feasible next stop found."
            )

        _, chosen_index, chosen_stop = min(
            candidates,
            key=lambda item: (item[0], item[1]),
        )

        result.append(chosen_stop)

        remaining = [
            (index, stop)
            for index, stop in remaining
            if index != chosen_index
        ]

        order_id, kind = stop_key(chosen_stop)
        order = order_map[order_id]

        if kind == "pickup":
            picked_up.add(order_id)
            weight += order.weight_kg
            volume += order.volume_m3

        else:
            weight -= order.weight_kg
            volume -= order.volume_m3

    validate_sequence(result, orders, vehicle)

    return result


def context_fingerprint(route, trip, orders, vehicle):
    """
    Identify the exact route and cargo assumptions
    used to produce a preview.
    """
    payload = {
        "route_id": str(route.id),
        "route_updated": route.calculated_at.isoformat(),
        "route_distance": route.distance_m,
        "route_duration": route.duration_s,
        "route_source": route.source,
        "route_stops": [
            [
                str(stop.order_id),
                stop.kind,
                stop.address,
                stop.latitude,
                stop.longitude,
            ]
            for stop in route.stops
        ],
        "trip_id": str(trip.id),
        "trip_status": trip.status.value,
        "trip_orders": [
            str(order_id)
            for order_id in trip.order_ids
        ],
        "cargo": sorted([
            [
                str(order.id),
                order.weight_kg,
                order.volume_m3,
            ]
            for order in orders
        ]),
        "vehicle": [
            str(vehicle.id),
            vehicle.capacity_kg,
            vehicle.volume_capacity_m3,
        ],
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def preview_token(
    route, trip, orders, vehicle,
    optimized_stops, measurement,
):
    """
    Include both the source snapshot and the candidate.
    Applying a different candidate requires a new preview.
    """
    candidate = {
        "context": context_fingerprint(
            route, trip, orders, vehicle
        ),
        "stops": [
            list(stop_key(stop))
            for stop in optimized_stops
        ],
        "distance_m": measurement["distance_m"],
        "duration_s": measurement["duration_s"],
        "source": measurement["source"],
    }

    encoded = json.dumps(
        candidate,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def response_variant(
    stops, measurement, straight_line_m,
):
    return SequenceVariantResponse(
        stops=[
            RouteStopResponse(
                order_id=str(stop.order_id),
                kind=stop.kind,
                address=stop.address,
                latitude=stop.latitude,
                longitude=stop.longitude,
            )
            for stop in stops
        ],
        distance_km=round(
            measurement["distance_m"] / 1000, 3
        ),
        duration_minutes=round(
            measurement["duration_s"] / 60, 1
        ),
        straight_line_km=round(
            straight_line_m / 1000, 3
        ),
        source=measurement["source"],
    )


def build_response(
    trip_id,
    original_stops,
    optimized_stops,
    original_measurement,
    optimized_measurement,
    original_proxy,
    optimized_proxy,
    *,
    applied=False,
    token=None,
    applied_at=None,
):
    if (
        original_measurement["source"]
        != optimized_measurement["source"]
    ):
        raise SequenceUnavailableError(
            "Cannot compare Geoapify road distances "
            "against offline demo estimates. "
            "Try again when Geoapify is available."
        )

    original_distance = original_measurement[
        "distance_m"
    ]

    optimized_distance = optimized_measurement[
        "distance_m"
    ]

    saved_m = (
        original_distance - optimized_distance
    )

    saved_s = (
        original_measurement["duration_s"]
        - optimized_measurement["duration_s"]
    )

    changed = (
        [stop_key(s) for s in original_stops]
        != [stop_key(s) for s in optimized_stops]
    )

    # Require more than 1 metre of measured savings.
    can_apply = (
        not applied
        and changed
        and saved_m > 1.0
    )

    percent = (
        saved_m / original_distance * 100
        if original_distance > 0
        else 0
    )

    return StopSequenceResponse(
        trip_id=str(trip_id),
        is_applied=applied,
        sequence_changed=changed,
        can_apply=can_apply,
        preview_token=(
            token if can_apply else None
        ),
        original=response_variant(
            original_stops,
            original_measurement,
            original_proxy,
        ),
        optimized=response_variant(
            optimized_stops,
            optimized_measurement,
            optimized_proxy,
        ),
        distance_saved_km=round(saved_m / 1000, 3),
        time_saved_minutes=round(saved_s / 60, 1),
        distance_saved_percent=round(percent, 2),
        applied_at=applied_at,
    )


async def load_context(trip_id, session=None):
    if not ObjectId.is_valid(trip_id):
        raise SequenceNotFoundError(
            "Trip not found."
        )

    trip = await Trip.get(
        ObjectId(trip_id),
        session=session,
    )

    if trip is None:
        raise SequenceNotFoundError(
            "Trip not found."
        )

    route = await TripRoute.find_one(
        TripRoute.trip_id == trip.id,
        session=session,
    )

    if route is None:
        raise SequenceNotFoundError(
            "Calculate the F12 route first."
        )

    vehicle = await Vehicle.get(
        trip.vehicle_id,
        session=session,
    )

    if vehicle is None:
        raise SequenceValidationError(
            "Trip vehicle no longer exists."
        )

    orders = []

    for order_id in trip.order_ids:
        order = await Order.get(
            order_id,
            session=session,
        )

        if order is None:
            raise SequenceValidationError(
                "One of the trip orders no longer exists."
            )

        orders.append(order)

    return trip, route, vehicle, orders


def get_original_measurement(route):
    return {
        "distance_m": route.distance_m,
        "duration_s": route.duration_s,
        "source": route.source,
    }


async def prepare_preview(trip_id):
    trip, route, vehicle, orders = (
        await load_context(trip_id)
    )

    if trip.status != TripStatus.DISPATCHED:
        raise SequenceConflictError(
            "Only dispatched trips can be optimized."
        )

    if route.optimized_at is not None:
        raise SequenceConflictError(
            "This trip already has an applied "
            "optimized stop sequence."
        )

    original_stops = list(route.stops)

    optimized_stops = nearest_neighbour_sequence(
        original_stops,
        orders,
        vehicle,
    )

    original_measurement = (
        get_original_measurement(route)
    )

    original_proxy = straight_line_distance_m(
        original_stops
    )

    optimized_proxy = straight_line_distance_m(
        optimized_stops
    )

    same_sequence = (
        [stop_key(s) for s in original_stops]
        == [stop_key(s) for s in optimized_stops]
    )

    if same_sequence:
        measurement = {
            **original_measurement,
            "geometry": route.geometry,
        }

    else:
        try:
            measurement = await calculate_geoapify_route(
                optimized_stops,
                use_live_api=(
                    route.source == "geoapify"
                ),
            )

        except GeoapifyRouteError as exc:
            raise SequenceUnavailableError(
                str(exc)
            ) from exc

    token = preview_token(
        route, trip, orders, vehicle,
        optimized_stops, measurement,
    )

    response = build_response(
        trip.id,
        original_stops,
        optimized_stops,
        original_measurement,
        measurement,
        original_proxy,
        optimized_proxy,
        token=token,
    )

    return (
        response,
        optimized_stops,
        measurement,
        original_proxy,
        optimized_proxy,
    )


async def preview_sequence(trip_id):
    response, *_ = await prepare_preview(trip_id)
    return response


async def get_saved_sequence(trip_id):
    if not ObjectId.is_valid(trip_id):
        raise SequenceNotFoundError(
            "Trip not found."
        )

    trip = await Trip.get(ObjectId(trip_id))

    if trip is None:
        raise SequenceNotFoundError(
            "Trip not found."
        )

    route = await TripRoute.find_one(
        TripRoute.trip_id == trip.id
    )

    if (
        route is None
        or route.optimized_at is None
        or not route.original_stops
        or route.original_distance_m is None
        or route.original_duration_s is None
        or route.original_source is None
    ):
        raise SequenceNotFoundError(
            "No optimized sequence saved yet."
        )

    return build_response(
        trip.id,
        route.original_stops,
        route.stops,
        {
            "distance_m": route.original_distance_m,
            "duration_s": route.original_duration_s,
            "source": route.original_source,
        },
        get_original_measurement(route),
        (
            route.original_straight_line_m
            if route.original_straight_line_m is not None
            else straight_line_distance_m(
                route.original_stops
            )
        ),
        (
            route.optimized_straight_line_m
            if route.optimized_straight_line_m is not None
            else straight_line_distance_m(
                route.stops
            )
        ),
        applied=True,
        applied_at=route.optimized_at,
    )


async def apply_sequence(trip_id, supplied_token):
    (
        response,
        optimized_stops,
        measurement,
        original_proxy,
        optimized_proxy,
    ) = await prepare_preview(trip_id)

    if not response.can_apply:
        raise SequenceConflictError(
            "No shorter route was found. "
            "The F12 route is unchanged."
        )

    if supplied_token != response.preview_token:
        raise SequenceConflictError(
            "The route preview has changed. "
            "Preview again before applying."
        )

    now = datetime.now(timezone.utc)

    try:
        async with client.start_session() as session:
            async with await session.start_transaction():
                (
                    trip,
                    route,
                    vehicle,
                    orders,
                ) = await load_context(
                    trip_id,
                    session=session,
                )

                if trip.status != TripStatus.DISPATCHED:
                    raise SequenceConflictError(
                        "The trip is no longer dispatched."
                    )

                if route.optimized_at is not None:
                    raise SequenceConflictError(
                        "A sequence is already applied."
                    )

                # Recheck the exact candidate inside
                # the transaction before changing data.
                current_token = preview_token(
                    route, trip, orders, vehicle,
                    optimized_stops, measurement,
                )

                if current_token != supplied_token:
                    raise SequenceConflictError(
                        "Trip, cargo or F12 route changed. "
                        "Preview again."
                    )

                # Save original F12 values first.
                route.original_stops = deepcopy(
                    route.stops
                )
                route.original_geometry = deepcopy(
                    route.geometry
                )
                route.original_distance_m = (
                    route.distance_m
                )
                route.original_duration_s = (
                    route.duration_s
                )
                route.original_source = route.source
                route.original_straight_line_m = (
                    original_proxy
                )
                route.optimized_straight_line_m = (
                    optimized_proxy
                )

                # Apply optimized F13 values.
                route.stops = optimized_stops
                route.geometry = deepcopy(
                    measurement["geometry"]
                )
                route.distance_m = measurement[
                    "distance_m"
                ]
                route.duration_s = measurement[
                    "duration_s"
                ]
                route.source = measurement[
                    "source"
                ]
                route.calculated_at = now
                route.optimized_at = now

                await route.save(session=session)

                # Update the existing F11 trip.
                trip.estimated_distance_km = round(
                    measurement["distance_m"] / 1000,
                    3,
                )
                trip.updated_at = now

                await trip.save(session=session)

    except PyMongoError as exc:
        if exc.has_error_label(
            "TransientTransactionError"
        ):
            raise SequenceConflictError(
                "Concurrent route update detected. "
                "Reload and preview again."
            ) from exc

        raise

    return response.model_copy(
        update={
            "is_applied": True,
            "can_apply": False,
            "preview_token": None,
            "applied_at": now,
        }
    )
import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.trip import Trip, TripStatus
from app.models.order import Order
from app.models.route import RouteStop
from app.models.trip_route import TripRoute

from app.schemas.route_distance_and_time_schemas import (
    RouteStopResponse,
    TripRouteResponse,
    RouteStatusResponse,
)

from app.integrations.geoapify_routing_client import (
    GeoapifyRouteError,
    geocode_address,
    calculate_geoapify_route,
)


class RouteTripNotFoundError(Exception):
    pass


class RouteNotFoundError(Exception):
    pass


class RouteValidationError(Exception):
    pass


class RouteConflictError(Exception):
    pass


class RouteUnavailableError(Exception):
    pass


def validate_trip_id(trip_id):
    if not ObjectId.is_valid(trip_id):
        raise RouteTripNotFoundError(
            "Trip not found."
        )

    return ObjectId(trip_id)


async def get_trip_document(trip_id):
    trip = await Trip.get(validate_trip_id(trip_id))

    if trip is None:
        raise RouteTripNotFoundError(
            "Trip not found."
        )

    return trip


async def resolve_stop(
    order,
    kind,
):
    if kind == "pickup":
        address = order.pickup_address
        latitude = getattr(
            order, "pickup_latitude", None
        )
        longitude = getattr(
            order, "pickup_longitude", None
        )
    else:
        address = order.delivery_address
        latitude = getattr(
            order, "delivery_latitude", None
        )
        longitude = getattr(
            order, "delivery_longitude", None
        )

    if latitude is not None and longitude is not None:
        source = "saved"
    else:
        latitude, longitude, source = await geocode_address(
            address
        )

    stop = RouteStop(
        order_id=order.id,
        kind=kind,
        address=address,
        latitude=latitude,
        longitude=longitude,
    )

    return stop, source


async def get_trip_stops(trip):
    """
    F12's initial order:
    pickup -> delivery for each assigned order.

    F13 will later optimize stop ordering while
    preserving pickup-before-delivery precedence.
    """
    orders = []

    for order_id in trip.order_ids:
        order = await Order.get(order_id)

        if order is None:
            raise RouteValidationError(
                "A trip order no longer exists."
            )

        orders.append(order)

    requests = []

    for order in orders:
        requests.append(resolve_stop(order, "pickup"))
        requests.append(resolve_stop(order, "delivery"))

    if len(requests) < 2:
        raise RouteValidationError(
            "The trip has insufficient route stops."
        )

    results = await asyncio.gather(*requests)

    stops = [stop for stop, _ in results]

    # If any coordinate comes from the sample,
    # do not present the result as a real road route.
    has_demo_coordinates = any(
        source == "demo"
        for _, source in results
    )

    return stops, has_demo_coordinates


def route_to_response(
    route,
    from_saved_route=False,
):
    return TripRouteResponse(
        id=str(route.id),
        trip_id=str(route.trip_id),
        distance_km=round(route.distance_m / 1000, 3),
        duration_minutes=round(route.duration_s / 60, 1),
        source=route.source,
        is_estimate=route.source == "demo_estimate",
        from_saved_route=from_saved_route,
        stops=[
            RouteStopResponse(
                order_id=str(stop.order_id),
                kind=stop.kind,
                address=stop.address,
                latitude=stop.latitude,
                longitude=stop.longitude,
            )
            for stop in route.stops
        ],
        geometry=route.geometry,
        calculated_at=route.calculated_at,
    )


async def get_route(trip_id):
    trip = await get_trip_document(trip_id)

    route = await TripRoute.find_one(
        TripRoute.trip_id == trip.id
    )

    if route is None:
        raise RouteNotFoundError(
            "No route has been calculated for this trip."
        )

    return route_to_response(
        route,
        from_saved_route=True,
    )


async def get_route_status(trip_id):
    trip = await get_trip_document(trip_id)

    route = await TripRoute.find_one(
        TripRoute.trip_id == trip.id
    )

    return RouteStatusResponse(
        trip_id=str(trip.id),
        calculated=route is not None,
        source=route.source if route else None,
    )


async def calculate_trip_route(
    trip_id,
    force_refresh=False,
):
    trip = await get_trip_document(trip_id)

    if trip.status == TripStatus.CANCELLED:
        raise RouteConflictError(
            "A cancelled trip cannot be routed."
        )

    existing = await TripRoute.find_one(
        TripRoute.trip_id == trip.id
    )

    # F13: Preserve optimized route ordering.
    if (
        existing is not None
        and existing.optimized_at is not None
        and force_refresh
    ):
        raise RouteConflictError(
            "This trip has an optimized F13 route. "
            "F12 recalculation is blocked to preserve "
            "the saved stop sequence."
        )

    if existing is not None and not force_refresh:
        return route_to_response(
            existing,
            from_saved_route=True,
        )

    try:
        stops, has_demo_coordinates = await get_trip_stops(
            trip
        )

        calculated = await calculate_geoapify_route(
            stops,
            force_refresh=force_refresh,
            use_live_api=not has_demo_coordinates,
        )

    except GeoapifyRouteError as exc:
        raise RouteUnavailableError(str(exc)) from exc

    # Never overwrite an existing verified road route
    # with an approximate result after an API failure.
    if (
        existing is not None
        and existing.source == "geoapify"
        and calculated["source"] != "geoapify"
    ):
        return route_to_response(
            existing,
            from_saved_route=True,
        )

    calculated_at = datetime.now(timezone.utc)

    if existing is None:
        route = TripRoute(
            trip_id=trip.id,
            stops=stops,
            geometry=calculated["geometry"],
            distance_m=calculated["distance_m"],
            duration_s=calculated["duration_s"],
            source=calculated["source"],
            calculated_at=calculated_at,
        )

        try:
            await route.insert()
        except DuplicateKeyError as exc:
            raise RouteConflictError(
                "This trip was routed concurrently. "
                "Reload and view the saved route."
            ) from exc

    else:
        route = existing

        route.stops = stops
        route.geometry = calculated["geometry"]
        route.distance_m = calculated["distance_m"]
        route.duration_s = calculated["duration_s"]
        route.source = calculated["source"]
        route.calculated_at = calculated_at

        await route.save()

    # F11/F5/F15 share this estimated-distance field.
    # Actual trip distance is intentionally untouched.
    trip.estimated_distance_km = round(
        calculated["distance_m"] / 1000,
        3,
    )
    trip.updated_at = calculated_at

    await trip.save()

    return route_to_response(route)
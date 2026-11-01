import asyncio
import logging
import math
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.driver import Driver
from app.models.user import Role
from app.models.trip import Trip, TripStatus
from app.models.trip_route import TripRoute
from app.models.vehicle import Vehicle
from app.models.position_update import (
    PositionUpdate,
    GPSStatus,
)

from app.schemas.simulated_gps_schemas import (
    GPSTripItem,
    GPSTripListResponse,
    GPSPositionResponse,
)

from app.integrations.geoapify_routing_client import (
    haversine_m,
)


logger = logging.getLogger(__name__)

GPS_INTERVAL_SECONDS = 5

_gps_lock = asyncio.Lock()


class GPSNotFoundError(Exception):
    pass


class GPSForbiddenError(Exception):
    pass


class GPSConflictError(Exception):
    pass


class GPSValidationError(Exception):
    pass


def utc_datetime(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def same_route_version(first, second):
    return (
        utc_datetime(first)
        == utc_datetime(second)
    )


def parse_route_points(geometry):
    """
    Read F12/F13 GeoJSON geometry.

    GeoJSON coordinates are [longitude, latitude].
    Our internal points are (latitude, longitude).

    Multiple line segments are joined in their
    stored order. No external routing calls occur.
    """
    if not isinstance(geometry, dict):
        raise GPSValidationError(
            "Invalid saved route geometry."
        )

    route_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if route_type == "LineString":
        lines = [coordinates]

    elif route_type == "MultiLineString":
        lines = coordinates

    else:
        raise GPSValidationError(
            "Expected LineString or MultiLineString geometry."
        )

    if not isinstance(lines, list):
        raise GPSValidationError(
            "Saved route coordinates are missing."
        )

    points = []

    for line in lines:
        if not isinstance(line, list):
            raise GPSValidationError(
                "Invalid route line."
            )

        for coordinate in line:
            if (
                not isinstance(coordinate, (list, tuple))
                or len(coordinate) < 2
            ):
                raise GPSValidationError(
                    "Invalid coordinate pair."
                )

            try:
                longitude = float(coordinate[0])
                latitude = float(coordinate[1])

            except (TypeError, ValueError) as exc:
                raise GPSValidationError(
                    "Route contains invalid coordinates."
                ) from exc

            if not (
                math.isfinite(latitude)
                and math.isfinite(longitude)
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                raise GPSValidationError(
                    "Route coordinate is out of range."
                )

            point = (latitude, longitude)

            if not points or points[-1] != point:
                points.append(point)

            if len(points) > 20000:
                raise GPSValidationError(
                    "Saved route contains too many coordinates."
                )

    if len(points) < 2:
        raise GPSValidationError(
            "Route needs at least two different points."
        )

    if route_length_m(points) <= 0:
        raise GPSValidationError(
            "Saved route has zero length."
        )

    return points


def route_length_m(points):
    return sum(
        haversine_m(
            first[0],
            first[1],
            second[0],
            second[1],
        )
        for first, second in zip(points, points[1:])
    )


def point_at_distance(points, distance_m):
    """
    Interpolate a position along the saved polyline.
    """
    if distance_m <= 0:
        return points[0]

    remaining = distance_m

    for first, second in zip(points, points[1:]):
        segment_m = haversine_m(
            first[0],
            first[1],
            second[0],
            second[1],
        )

        if segment_m <= 0:
            continue

        if remaining <= segment_m:
            fraction = remaining / segment_m

            latitude = (
                first[0]
                + (second[0] - first[0]) * fraction
            )

            longitude = (
                first[1]
                + (second[1] - first[1]) * fraction
            )

            return latitude, longitude

        remaining -= segment_m

    return points[-1]


def advance_simulated_position(
    position,
    points,
    seconds=GPS_INTERVAL_SECONDS,
):
    """
    Pure movement calculation.

    A 5-second tick advances:
        speed_kmh * 1000 / 3600 * 5 metres.

    The position never goes beyond the last point.
    """
    if position.status != GPSStatus.RUNNING:
        return position

    total_m = route_length_m(points)

    distance_per_second = (
        position.speed_kmh * 1000 / 3600
    )

    next_progress = min(
        total_m,
        position.progress_m
        + distance_per_second * seconds,
    )

    latitude, longitude = point_at_distance(
        points,
        next_progress,
    )

    position.latitude = latitude
    position.longitude = longitude
    position.progress_m = next_progress
    position.tick_count += 1
    position.updated_at = datetime.now(timezone.utc)

    if next_progress >= total_m:
        position.status = GPSStatus.FINISHED

    return position


def position_to_response(
    trip,
    route,
    position=None,
):
    points = parse_route_points(route.geometry)
    total_geometry_m = route_length_m(points)

    if position is None:
        latitude, longitude = points[0]
        status = "not_started"
        speed_kmh = 30.0
        progress_m = 0.0
        tick_count = 0
        updated_at = None

    else:
        latitude = position.latitude
        longitude = position.longitude
        status = position.status.value
        speed_kmh = position.speed_kmh
        progress_m = position.progress_m
        tick_count = position.tick_count
        updated_at = position.updated_at

        if (
            trip.status != TripStatus.DISPATCHED
            and position.status in (
                GPSStatus.RUNNING,
                GPSStatus.PAUSED,
                GPSStatus.IDLE,
            )
        ):
            status = GPSStatus.STOPPED.value

    progress = min(
        1.0,
        max(0.0, progress_m / total_geometry_m),
    )

    route_distance_km = route.distance_m / 1000
    travelled_km = route_distance_km * progress
    remaining_km = max(
        0.0,
        route_distance_km - travelled_km,
    )

    return GPSPositionResponse(
        trip_id=str(trip.id),
        vehicle_id=str(trip.vehicle_id),
        latitude=latitude,
        longitude=longitude,
        status=status,
        speed_kmh=speed_kmh,
        progress_percent=round(progress * 100, 2),
        route_distance_km=round(
            route_distance_km, 3
        ),
        travelled_route_km=round(
            travelled_km, 3
        ),
        remaining_route_km=round(
            remaining_km, 3
        ),
        tick_count=tick_count,
        updated_at=updated_at,
        trip_status=trip.status.value,
    )


async def driver_for_user(user):
    return await Driver.find_one(
        Driver.user_id == user.id
    )


async def get_trip_context(
    trip_id,
    current_user,
):
    if not ObjectId.is_valid(trip_id):
        raise GPSNotFoundError(
            "Trip not found."
        )

    trip = await Trip.get(
        ObjectId(trip_id)
    )

    if trip is None:
        raise GPSNotFoundError(
            "Trip not found."
        )

    if current_user.role == Role.DRIVER:
        driver = await driver_for_user(current_user)

        if (
            driver is None
            or driver.id != trip.driver_id
        ):
            raise GPSForbiddenError(
                "This trip is not assigned to your "
                "Driver account."
            )

    route = await TripRoute.find_one(
        TripRoute.trip_id == trip.id
    )

    if route is None:
        raise GPSNotFoundError(
            "No saved route exists. "
            "Calculate F12 first."
        )

    return trip, route


async def list_gps_trips(
    current_user,
    page=1,
    page_size=100,
):
    filters = {}

    if current_user.role == Role.DRIVER:
        driver = await driver_for_user(
            current_user
        )

        if driver is None:
            return GPSTripListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
            )

        filters["driver_id"] = driver.id

    query = Trip.find(filters)

    total = await query.count()

    trips = await (
        query.sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    items = []

    for trip in trips:
        vehicle = await Vehicle.get(
            trip.vehicle_id
        )

        driver = await Driver.get(
            trip.driver_id
        )

        route = await TripRoute.find_one(
            TripRoute.trip_id == trip.id
        )

        items.append(
            GPSTripItem(
                id=str(trip.id),
                vehicle_registration=(
                    vehicle.registration_number
                    if vehicle else "Unknown vehicle"
                ),
                driver_name=(
                    driver.full_name
                    if driver else "Unknown driver"
                ),
                order_count=len(trip.order_ids),
                trip_status=trip.status.value,
                route_available=route is not None,
            )
        )

    return GPSTripListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_gps_position(
    trip_id,
    current_user,
):
    trip, route = await get_trip_context(
        trip_id,
        current_user,
    )

    position = await PositionUpdate.find_one(
        PositionUpdate.trip_id == trip.id
    )

    return position_to_response(
        trip,
        route,
        position,
    )


async def start_simulation(
    trip_id,
    current_user,
    speed_kmh,
):
    async with _gps_lock:
        trip, route = await get_trip_context(
            trip_id,
            current_user,
        )

        if trip.status != TripStatus.DISPATCHED:
            raise GPSConflictError(
                "Only dispatched trips can be simulated."
            )

        points = parse_route_points(route.geometry)

        position = await PositionUpdate.find_one(
            PositionUpdate.trip_id == trip.id
        )

        now = datetime.now(timezone.utc)

        if position is None:
            position = PositionUpdate(
                trip_id=trip.id,
                latitude=points[0][0],
                longitude=points[0][1],
                status=GPSStatus.RUNNING,
                progress_m=0,
                speed_kmh=speed_kmh,
                tick_count=0,
                route_calculated_at=route.calculated_at,
                updated_at=now,
            )

            try:
                await position.insert()
            except DuplicateKeyError as exc:
                raise GPSConflictError(
                    "Simulation was started concurrently. "
                    "Reload the page."
                ) from exc

        else:
            if position.status == GPSStatus.RUNNING:
                raise GPSConflictError(
                    "Simulation is already running."
                )

            route_changed = not same_route_version(
                position.route_calculated_at,
                route.calculated_at,
            )

            if (
                position.status in (
                    GPSStatus.FINISHED,
                    GPSStatus.STOPPED,
                )
                or route_changed
            ):
                position.progress_m = 0
                position.tick_count = 0
                position.latitude = points[0][0]
                position.longitude = points[0][1]

            position.route_calculated_at = (
                route.calculated_at
            )
            position.speed_kmh = speed_kmh
            position.status = GPSStatus.RUNNING
            position.updated_at = now

            await position.save()

        return position_to_response(
            trip,
            route,
            position,
        )


async def pause_simulation(
    trip_id,
    current_user,
):
    async with _gps_lock:
        trip, route = await get_trip_context(
            trip_id,
            current_user,
        )

        position = await PositionUpdate.find_one(
            PositionUpdate.trip_id == trip.id
        )

        if (
            position is None
            or position.status != GPSStatus.RUNNING
        ):
            raise GPSConflictError(
                "No running simulation to pause."
            )

        position.status = GPSStatus.PAUSED
        position.updated_at = datetime.now(
            timezone.utc
        )

        await position.save()

        return position_to_response(
            trip,
            route,
            position,
        )


async def reset_simulation(
    trip_id,
    current_user,
):
    async with _gps_lock:
        trip, route = await get_trip_context(
            trip_id,
            current_user,
        )

        if trip.status != TripStatus.DISPATCHED:
            raise GPSConflictError(
                "Cannot reset a completed or "
                "cancelled trip."
            )

        points = parse_route_points(route.geometry)

        position = await PositionUpdate.find_one(
            PositionUpdate.trip_id == trip.id
        )

        now = datetime.now(timezone.utc)

        if position is None:
            position = PositionUpdate(
                trip_id=trip.id,
                latitude=points[0][0],
                longitude=points[0][1],
                status=GPSStatus.IDLE,
                progress_m=0,
                speed_kmh=30,
                tick_count=0,
                route_calculated_at=route.calculated_at,
                updated_at=now,
            )

            try:
                await position.insert()
            except DuplicateKeyError as exc:
                raise GPSConflictError(
                    "Simulation was modified concurrently."
                ) from exc

        else:
            position.latitude = points[0][0]
            position.longitude = points[0][1]
            position.progress_m = 0
            position.tick_count = 0
            position.status = GPSStatus.IDLE
            position.route_calculated_at = (
                route.calculated_at
            )
            position.updated_at = now

            await position.save()

        return position_to_response(
            trip,
            route,
            position,
        )


async def tick_running_simulations():
    """
    Called by the backend every five seconds.

    Updates one saved GPS position per trip.
    Also stops paused/running simulations when
    their trip is completed or cancelled.
    """
    positions = await PositionUpdate.find({
        "status": {
            "$in": [
                GPSStatus.RUNNING.value,
                GPSStatus.PAUSED.value,
            ]
        }
    }).to_list()

    for item in positions:
        try:
            async with _gps_lock:
                position = await PositionUpdate.get(
                    item.id
                )

                if (
                    position is None
                    or position.status not in (
                        GPSStatus.RUNNING,
                        GPSStatus.PAUSED,
                    )
                ):
                    continue

                trip = await Trip.get(
                    position.trip_id
                )

                if (
                    trip is None
                    or trip.status
                    != TripStatus.DISPATCHED
                ):
                    position.status = GPSStatus.STOPPED
                    position.updated_at = datetime.now(
                        timezone.utc
                    )

                    await position.save()
                    continue

                route = await TripRoute.find_one(
                    TripRoute.trip_id == trip.id
                )

                if (
                    route is None
                    or not same_route_version(
                        position.route_calculated_at,
                        route.calculated_at,
                    )
                ):
                    position.status = GPSStatus.STOPPED
                    position.updated_at = datetime.now(
                        timezone.utc
                    )

                    await position.save()
                    continue

                if position.status == GPSStatus.PAUSED:
                    continue

                try:
                    points = parse_route_points(
                        route.geometry
                    )

                except GPSValidationError:
                    position.status = GPSStatus.STOPPED
                    position.updated_at = datetime.now(
                        timezone.utc
                    )

                    await position.save()
                    continue

                advance_simulated_position(
                    position,
                    points,
                )

                await position.save()

        except Exception:
            logger.exception(
                "F14 GPS update failed for trip %s",
                item.trip_id,
            )
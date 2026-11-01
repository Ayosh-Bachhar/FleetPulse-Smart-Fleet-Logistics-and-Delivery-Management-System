import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.access_control import (
    get_current_user,
    require_csrf,
)
from app.controllers.simulated_gps_controller import router

from app.models.user import Role
from app.models.trip import TripStatus
from app.models.position_update import (
    PositionUpdate,
    GPSStatus,
)

from app.schemas.simulated_gps_schemas import (
    GPSPositionResponse,
    GPSTripListResponse,
)

from app.services.simulated_gps_service import (
    GPSForbiddenError,
    GPSValidationError,
    advance_simulated_position,
    get_trip_context,
    parse_route_points,
    point_at_distance,
    position_to_response,
    route_length_m,
    same_route_version,
)


TRIP_ID = "507f1f77bcf86cd799439010"
USER_ID = "507f1f77bcf86cd799439011"
DRIVER_ID = "507f1f77bcf86cd799439012"
OTHER_DRIVER_ID = "507f1f77bcf86cd799439013"
VEHICLE_ID = "507f1f77bcf86cd799439014"

URL = f"/api/v1/gps/trips/{TRIP_ID}"


def geometry():
    return {
        "type": "MultiLineString",
        "coordinates": [
            [
                [90.30, 23.80],
                [90.31, 23.80],
            ],
            [
                [90.31, 23.80],
                [90.32, 23.80],
            ],
        ],
    }


def sample_trip():
    return SimpleNamespace(
        id=ObjectId(TRIP_ID),
        vehicle_id=ObjectId(VEHICLE_ID),
        driver_id=ObjectId(DRIVER_ID),
        status=TripStatus.DISPATCHED,
    )


def sample_route():
    return SimpleNamespace(
        geometry=geometry(),
        distance_m=2500,
        calculated_at=datetime.now(timezone.utc),
    )


def sample_position(status=GPSStatus.RUNNING):
    points = parse_route_points(geometry())

    return SimpleNamespace(
        trip_id=ObjectId(TRIP_ID),
        latitude=points[0][0],
        longitude=points[0][1],
        status=status,
        progress_m=0,
        speed_kmh=36,
        tick_count=0,
        route_calculated_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def sample_response():
    return position_to_response(
        sample_trip(),
        sample_route(),
        sample_position(),
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
        ] = lambda: SimpleNamespace(
            id=ObjectId(USER_ID),
            role=role,
        )

    if skip_csrf:
        app.dependency_overrides[
            require_csrf
        ] = lambda: None

    return app


def test_existing_position_model_defaults():
    position = PositionUpdate.model_construct(
        trip_id=ObjectId(TRIP_ID),
        latitude=23.8,
        longitude=90.3,
        route_calculated_at=datetime.now(timezone.utc),
    )

    assert position.status == GPSStatus.IDLE
    assert position.progress_m == 0
    assert position.tick_count == 0


def test_multiline_geometry_is_flattened():
    points = parse_route_points(geometry())

    assert len(points) == 3
    assert points[0] == (23.80, 90.30)
    assert points[-1] == (23.80, 90.32)


def test_linestring_geometry_supported():
    points = parse_route_points({
        "type": "LineString",
        "coordinates": [
            [90.3, 23.8],
            [90.4, 23.8],
        ],
    })

    assert len(points) == 2


@pytest.mark.parametrize(
    "broken",
    [
        {},
        {
            "type": "Point",
            "coordinates": [90.3, 23.8],
        },
        {
            "type": "LineString",
            "coordinates": [[90.3, 23.8]],
        },
        {
            "type": "LineString",
            "coordinates": [
                [200, 23.8],
                [90.4, 23.8],
            ],
        },
        {
            "type": "MultiLineString",
            "coordinates": [],
        },
    ],
)
def test_invalid_route_geometry_rejected(broken):
    with pytest.raises(GPSValidationError):
        parse_route_points(broken)


def test_route_length_positive():
    points = parse_route_points(geometry())

    assert route_length_m(points) > 1000


def test_position_at_start_and_end():
    points = parse_route_points(geometry())
    total_m = route_length_m(points)

    assert point_at_distance(
        points, 0
    ) == points[0]

    assert point_at_distance(
        points, total_m + 100
    ) == points[-1]


def test_position_interpolation():
    points = parse_route_points(geometry())

    halfway = point_at_distance(
        points,
        route_length_m(points) / 2,
    )

    assert halfway[0] == pytest.approx(
        23.8,
        abs=0.00001,
    )

    assert halfway[1] == pytest.approx(
        90.31,
        abs=0.0001,
    )


def test_five_second_movement():
    points = parse_route_points(geometry())
    position = sample_position()

    advance_simulated_position(
        position,
        points,
        seconds=5,
    )

    # 36 km/h = 10 m/s; 5 seconds = 50 metres.
    assert position.progress_m == pytest.approx(50)
    assert position.tick_count == 1
    assert position.status == GPSStatus.RUNNING


def test_paused_position_does_not_advance():
    points = parse_route_points(geometry())
    position = sample_position(GPSStatus.PAUSED)

    advance_simulated_position(
        position, points, seconds=5
    )

    assert position.progress_m == 0
    assert position.tick_count == 0


def test_simulation_stops_at_final_point():
    points = parse_route_points(geometry())
    position = sample_position()

    advance_simulated_position(
        position,
        points,
        seconds=10000,
    )

    assert position.status == GPSStatus.FINISHED
    assert position.tick_count == 1
    assert position.progress_m == pytest.approx(
        route_length_m(points)
    )

    assert (
        position.latitude,
        position.longitude,
    ) == points[-1]


def test_finished_position_stays_finished():
    points = parse_route_points(geometry())
    position = sample_position(GPSStatus.FINISHED)

    advance_simulated_position(
        position,
        points,
        seconds=5,
    )

    assert position.tick_count == 0


def test_unstarted_response():
    result = position_to_response(
        sample_trip(),
        sample_route(),
    )

    assert result.status == "not_started"
    assert result.progress_percent == 0
    assert result.tick_count == 0
    assert result.remaining_route_km == 2.5


def test_progress_and_remaining_distance():
    position = sample_position()
    position.progress_m = (
        route_length_m(
            parse_route_points(geometry())
        ) / 2
    )

    result = position_to_response(
        sample_trip(),
        sample_route(),
        position,
    )

    assert result.progress_percent == pytest.approx(50)
    assert result.travelled_route_km == pytest.approx(1.25)
    assert result.remaining_route_km == pytest.approx(1.25)


def test_completed_trip_reports_stopped():
    trip = sample_trip()
    trip.status = TripStatus.COMPLETED

    result = position_to_response(
        trip,
        sample_route(),
        sample_position(),
    )

    assert result.status == "stopped"


def test_route_version_timezone_normalization():
    aware = datetime(
        2030, 1, 1, 12,
        tzinfo=timezone.utc,
    )

    naive = datetime(
        2030, 1, 1, 12,
    )

    assert same_route_version(
        aware, naive
    )


def test_other_driver_cannot_read_trip():
    async def run():
        user = SimpleNamespace(
            id=ObjectId(USER_ID),
            role=Role.DRIVER,
        )

        other_driver = SimpleNamespace(
            id=ObjectId(OTHER_DRIVER_ID),
        )

        with (
            patch(
                "app.services.simulated_gps_service.Trip.get",
                new_callable=AsyncMock,
            ) as get_trip,
            patch(
                "app.services.simulated_gps_service.driver_for_user",
                new_callable=AsyncMock,
            ) as find_driver,
        ):
            get_trip.return_value = sample_trip()
            find_driver.return_value = other_driver

            with pytest.raises(GPSForbiddenError):
                await get_trip_context(TRIP_ID, user)

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER, Role.DRIVER],
)
def test_allowed_roles_can_view_position(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.simulated_gps_controller."
            "get_gps_position",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                response = await http.get(URL)

        assert response.status_code == 200
        assert response.json()["status"] == "running"

    asyncio.run(run())


def test_customer_cannot_view_gps():
    async def run():
        app = make_app(Role.CUSTOMER)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http:
            response = await http.get(URL)

        assert response.status_code == 403

    asyncio.run(run())


def test_unauthenticated_user_rejected():
    async def run():
        app = make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http:
            response = await http.get(URL)

        assert response.status_code == 401

    asyncio.run(run())


def test_dispatcher_can_start_simulation():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.simulated_gps_controller."
            "start_simulation",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                response = await http.post(
                    f"{URL}/start",
                    json={"speed_kmh": 30},
                )

        assert response.status_code == 200
        mocked.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DRIVER],
)
def test_nondispatchers_cannot_start(role):
    async def run():
        app = make_app(role)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http:
            response = await http.post(
                f"{URL}/start",
                json={"speed_kmh": 30},
            )

        assert response.status_code == 403

    asyncio.run(run())


def test_invalid_simulation_speed_rejected():
    async def run():
        app = make_app(Role.DISPATCHER)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http:
            response = await http.post(
                f"{URL}/start",
                json={"speed_kmh": 200},
            )

        assert response.status_code == 422

    asyncio.run(run())


@pytest.mark.parametrize(
    "action,service_name",
    [
        ("pause", "pause_simulation"),
        ("reset", "reset_simulation"),
    ],
)
def test_dispatcher_controls(action, service_name):
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.simulated_gps_controller."
            + service_name,
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                response = await http.post(
                    f"{URL}/{action}",
                )

        assert response.status_code == 200

    asyncio.run(run())


def test_start_requires_csrf():
    async def run():
        app = make_app(
            Role.DISPATCHER,
            skip_csrf=False,
        )

        with patch(
            "app.controllers.simulated_gps_controller."
            "start_simulation",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                response = await http.post(
                    f"{URL}/start",
                    json={"speed_kmh": 30},
                )

        assert response.status_code == 403
        mocked.assert_not_awaited()

    asyncio.run(run())
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
from app.models.user import Role
from app.models.route import RouteStop

from app.controllers.route_distance_and_time_controller import (
    router as route_router,
)

from app.schemas.route_distance_and_time_schemas import (
    TripRouteResponse,
)

from app.integrations.geoapify_routing_client import (
    build_demo_estimate,
    demo_coordinates,
    haversine_m,
    parse_geoapify_route,
    calculate_geoapify_route,
)

from app.services.route_distance_and_time_service import (
    RouteNotFoundError,
    RouteUnavailableError,
    route_to_response,
)


TRIP_ID = "507f1f77bcf86cd799439011"
ORDER_ID = "507f1f77bcf86cd799439012"
ROUTE_ID = "507f1f77bcf86cd799439013"
USER_ID = "507f1f77bcf86cd799439014"

URL = f"/api/v1/trips/{TRIP_ID}/route"


def sample_stops():
    return [
        RouteStop(
            order_id=ObjectId(ORDER_ID),
            kind="pickup",
            address="Uttara, Dhaka",
            latitude=23.8759,
            longitude=90.3795,
        ),
        RouteStop(
            order_id=ObjectId(ORDER_ID),
            kind="delivery",
            address="Mirpur, Dhaka",
            latitude=23.8041,
            longitude=90.3654,
        ),
    ]


def sample_route():
    stops = sample_stops()
    calculated = build_demo_estimate(stops)

    return SimpleNamespace(
        id=ObjectId(ROUTE_ID),
        trip_id=ObjectId(TRIP_ID),
        stops=stops,
        geometry=calculated["geometry"],
        distance_m=calculated["distance_m"],
        duration_s=calculated["duration_s"],
        source=calculated["source"],
        calculated_at=datetime.now(timezone.utc),
    )


def sample_response():
    return route_to_response(sample_route())


def make_app(role=None, bypass_csrf=True):
    app = FastAPI()

    app.include_router(
        route_router,
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


def test_sample_coordinates_exist():
    with patch(
        "app.integrations.geoapify_routing_client."
        "settings.GEOAPIFY_COUNTRY_CODE",
        "bd",
    ):
        result = demo_coordinates("Uttara, Dhaka")

    assert result is not None
    assert len(result) == 2


def test_haversine_distance():
    assert haversine_m(23.8, 90.4, 23.8, 90.4) == 0

    assert haversine_m(
        23.8759,
        90.3795,
        23.8041,
        90.3654,
    ) > 0


def test_demo_estimate_is_not_real_route():
    result = build_demo_estimate(sample_stops())

    assert result["source"] == "demo_estimate"
    assert result["distance_m"] > 0
    assert result["duration_s"] > 0

    assert (
        result["geometry"]["type"]
        == "MultiLineString"
    )


def test_geoapify_response_parser():
    body = {
        "features": [
            {
                "properties": {
                    "distance": 12500,
                    "time": 1800,
                },
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [
                        [
                            [90.3795, 23.8759],
                            [90.3654, 23.8041],
                        ]
                    ],
                },
            }
        ]
    }

    result = parse_geoapify_route(body)

    assert result["distance_m"] == 12500
    assert result["duration_s"] == 1800
    assert result["source"] == "geoapify"


def test_invalid_provider_result_rejected():
    from app.integrations.geoapify_routing_client import (
        GeoapifyRouteError,
    )

    with pytest.raises(GeoapifyRouteError):
        parse_geoapify_route({"features": []})


def test_route_response_units():
    result = sample_response()

    assert result.distance_km > 0
    assert result.duration_minutes > 0
    assert result.is_estimate
    assert result.trip_id == TRIP_ID


def test_offline_calculation():
    async def run():
        with patch(
            "app.integrations.geoapify_routing_client."
            "settings.GEOAPIFY_API_KEY",
            "",
        ):
            result = await calculate_geoapify_route(
                sample_stops()
            )

        assert result["source"] == "demo_estimate"

    asyncio.run(run())


def test_cached_real_route_reused():
    async def run():
        stored = {
            "distance_m": 12000,
            "duration_s": 1500,
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [
                    [
                        [90.3795, 23.8759],
                        [90.3654, 23.8041],
                    ]
                ],
            },
            "source": "geoapify",
        }

        with (
            patch(
                "app.integrations.geoapify_routing_client."
                "settings.GEOAPIFY_API_KEY",
                "test-key",
            ),
            patch(
                "app.integrations.geoapify_routing_client."
                "get_cached_payload",
                new_callable=AsyncMock,
            ) as mocked,
        ):
            mocked.return_value = stored

            result = await calculate_geoapify_route(
                sample_stops()
            )

        assert result == stored
        mocked.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER],
)
def test_staff_can_view_saved_route(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.route_distance_and_time_controller."
            "get_route",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(URL)

            assert response.status_code == 200
            assert response.json()["source"] == "demo_estimate"

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DRIVER],
)
def test_non_staff_denied(role):
    async def run():
        app = make_app(role)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 403

    asyncio.run(run())


def test_unauthenticated_denied():
    async def run():
        app = make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 401

    asyncio.run(run())


def test_dispatcher_can_calculate_route():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.route_distance_and_time_controller."
            "calculate_trip_route",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(URL)

            assert response.status_code == 200
            mocked.assert_awaited_once()

    asyncio.run(run())


def test_admin_cannot_calculate_route():
    async def run():
        app = make_app(Role.ADMIN)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(URL)

        assert response.status_code == 403

    asyncio.run(run())


def test_missing_route_returns_404():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.route_distance_and_time_controller."
            "get_route",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = RouteNotFoundError(
                "No saved route."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(URL)

            assert response.status_code == 404

    asyncio.run(run())


def test_provider_unavailable_returns_503():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.route_distance_and_time_controller."
            "calculate_trip_route",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = RouteUnavailableError(
                "Unable to resolve addresses."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(URL)

            assert response.status_code == 503

    asyncio.run(run())


def test_route_write_requires_csrf():
    async def run():
        app = make_app(
            Role.DISPATCHER,
            bypass_csrf=False,
        )

        with patch(
            "app.controllers.route_distance_and_time_controller."
            "calculate_trip_route",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(URL)

            assert response.status_code == 403
            mocked.assert_not_awaited()

    asyncio.run(run())
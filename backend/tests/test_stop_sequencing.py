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
from app.controllers.stop_sequencing_controller import router
from app.models.route import RouteStop
from app.models.trip import TripStatus
from app.models.trip_route import TripRoute
from app.models.user import Role

from app.services.stop_sequencing_service import (
    SequenceConflictError,
    SequenceUnavailableError,
    SequenceValidationError,
    build_response,
    nearest_neighbour_sequence,
    preview_token,
    stop_key,
    straight_line_distance_m,
    validate_sequence,
)


TRIP_ID = "507f1f77bcf86cd799439010"
ORDER_A = "507f1f77bcf86cd799439011"
ORDER_B = "507f1f77bcf86cd799439012"
USER_ID = "507f1f77bcf86cd799439013"
VEHICLE_ID = "507f1f77bcf86cd799439014"
ROUTE_ID = "507f1f77bcf86cd799439015"

URL = f"/api/v1/trips/{TRIP_ID}/stop-sequence"


def sample_stops():
    return [
        RouteStop(
            order_id=ObjectId(ORDER_A),
            kind="pickup",
            address="First pickup",
            latitude=0,
            longitude=0,
        ),
        RouteStop(
            order_id=ObjectId(ORDER_A),
            kind="delivery",
            address="First delivery",
            latitude=0,
            longitude=10,
        ),
        RouteStop(
            order_id=ObjectId(ORDER_B),
            kind="pickup",
            address="Second pickup",
            latitude=0,
            longitude=0.1,
        ),
        RouteStop(
            order_id=ObjectId(ORDER_B),
            kind="delivery",
            address="Second delivery",
            latitude=0,
            longitude=0.2,
        ),
    ]


def sample_orders():
    return [
        SimpleNamespace(
            id=ObjectId(ORDER_A),
            weight_kg=80,
            volume_m3=1.0,
        ),
        SimpleNamespace(
            id=ObjectId(ORDER_B),
            weight_kg=70,
            volume_m3=0.7,
        ),
    ]


def sample_vehicle(weight=200, volume=3):
    return SimpleNamespace(
        id=ObjectId(VEHICLE_ID),
        capacity_kg=weight,
        volume_capacity_m3=volume,
    )


def measurement(
    distance=10000,
    duration=1200,
    source="demo_estimate",
):
    return {
        "distance_m": distance,
        "duration_s": duration,
        "source": source,
    }


def sample_trip():
    return SimpleNamespace(
        id=ObjectId(TRIP_ID),
        status=TripStatus.DISPATCHED,
        order_ids=[
            ObjectId(ORDER_A),
            ObjectId(ORDER_B),
        ],
    )


def sample_route():
    return SimpleNamespace(
        id=ObjectId(ROUTE_ID),
        calculated_at=datetime.now(timezone.utc),
        distance_m=10000,
        duration_s=1200,
        source="demo_estimate",
        stops=sample_stops(),
    )


def sample_preview():
    original = sample_stops()

    optimized = nearest_neighbour_sequence(
        original,
        sample_orders(),
        sample_vehicle(),
    )

    return build_response(
        TRIP_ID,
        original,
        optimized,
        measurement(2500000, 40000),
        measurement(2200000, 36000),
        straight_line_distance_m(original),
        straight_line_distance_m(optimized),
        token="a" * 64,
    )


def make_app(role=None, skip_csrf=True):
    app = FastAPI()
    app.include_router(
        router,
        prefix="/api/v1",
    )

    if role is not None:
        app.dependency_overrides[get_current_user] = (
            lambda: SimpleNamespace(
                id=ObjectId(USER_ID),
                role=role,
            )
        )

    if skip_csrf:
        app.dependency_overrides[require_csrf] = (
            lambda: None
        )

    return app


def test_trip_route_keeps_f12_defaults():
    route = TripRoute.model_construct(
        trip_id=ObjectId(TRIP_ID),
        stops=sample_stops(),
        geometry={
            "type": "MultiLineString",
            "coordinates": [],
        },
        distance_m=10000,
        duration_s=1200,
        source="demo_estimate",
    )

    assert route.original_stops is None
    assert route.optimized_at is None
    assert route.distance_m == 10000


def test_nearest_neighbour_reorders_stops():
    result = nearest_neighbour_sequence(
        sample_stops(),
        sample_orders(),
        sample_vehicle(),
    )

    assert [stop_key(s) for s in result] == [
        (ORDER_A, "pickup"),
        (ORDER_B, "pickup"),
        (ORDER_B, "delivery"),
        (ORDER_A, "delivery"),
    ]


def test_first_pickup_remains_fixed():
    result = nearest_neighbour_sequence(
        sample_stops(),
        sample_orders(),
        sample_vehicle(),
    )

    assert stop_key(result[0]) == (
        ORDER_A, "pickup"
    )


def test_algorithm_is_deterministic():
    results = [
        [
            stop_key(s)
            for s in nearest_neighbour_sequence(
                sample_stops(),
                sample_orders(),
                sample_vehicle(),
            )
        ]
        for _ in range(5)
    ]

    assert all(
        item == results[0] for item in results
    )


def test_weight_capacity_changes_sequence():
    result = nearest_neighbour_sequence(
        sample_stops(),
        sample_orders(),
        sample_vehicle(weight=80),
    )

    assert stop_key(result[1]) == (
        ORDER_A, "delivery"
    )


def test_volume_capacity_changes_sequence():
    result = nearest_neighbour_sequence(
        sample_stops(),
        sample_orders(),
        sample_vehicle(volume=1),
    )

    assert stop_key(result[1]) == (
        ORDER_A, "delivery"
    )


def test_insufficient_capacity_rejected():
    with pytest.raises(
        SequenceValidationError,
        match="capacity",
    ):
        nearest_neighbour_sequence(
            sample_stops(),
            sample_orders(),
            sample_vehicle(weight=50),
        )


def test_delivery_before_pickup_rejected():
    stops = sample_stops()
    stops[0], stops[1] = stops[1], stops[0]

    with pytest.raises(
        SequenceValidationError,
        match="Delivery must follow",
    ):
        validate_sequence(
            stops,
            sample_orders(),
            sample_vehicle(),
        )


def test_missing_stop_rejected():
    with pytest.raises(
        SequenceValidationError,
        match="Exactly one pickup",
    ):
        validate_sequence(
            sample_stops()[:3],
            sample_orders(),
            sample_vehicle(),
        )


def test_duplicate_stop_rejected():
    stops = sample_stops()
    stops[-1] = stops[1]

    with pytest.raises(
        SequenceValidationError,
        match="Exactly one pickup",
    ):
        validate_sequence(
            stops,
            sample_orders(),
            sample_vehicle(),
        )


def test_missing_volume_capacity_rejected():
    with pytest.raises(
        SequenceValidationError,
        match="volume capacity",
    ):
        validate_sequence(
            sample_stops(),
            sample_orders(),
            sample_vehicle(volume=None),
        )


def test_optimized_proxy_distance_improves():
    original = sample_stops()

    optimized = nearest_neighbour_sequence(
        original,
        sample_orders(),
        sample_vehicle(),
    )

    assert (
        straight_line_distance_m(optimized)
        < straight_line_distance_m(original)
    )


def test_preview_reports_expected_savings():
    result = sample_preview()

    assert result.is_applied is False
    assert result.sequence_changed is True
    assert result.can_apply is True
    assert result.distance_saved_km == 300
    assert result.preview_token == "a" * 64


def test_worse_road_route_cannot_be_applied():
    original = sample_stops()

    optimized = nearest_neighbour_sequence(
        original,
        sample_orders(),
        sample_vehicle(),
    )

    response = build_response(
        TRIP_ID,
        original,
        optimized,
        measurement(10000, 1200),
        measurement(12000, 1300),
        10000,
        9000,
        token="b" * 64,
    )

    assert response.can_apply is False
    assert response.preview_token is None
    assert response.distance_saved_km < 0


def test_different_providers_cannot_be_compared():
    with pytest.raises(
        SequenceUnavailableError,
        match="Cannot compare",
    ):
        build_response(
            TRIP_ID,
            sample_stops(),
            sample_stops(),
            measurement(source="geoapify"),
            measurement(source="demo_estimate"),
            10000,
            10000,
        )


def test_preview_token_changes_with_capacity():
    route = sample_route()
    trip = sample_trip()

    optimized = nearest_neighbour_sequence(
        sample_stops(),
        sample_orders(),
        sample_vehicle(),
    )

    first = preview_token(
        route, trip, sample_orders(),
        sample_vehicle(), optimized,
        measurement(),
    )

    second = preview_token(
        route, trip, sample_orders(),
        sample_vehicle(weight=300), optimized,
        measurement(),
    )

    assert first != second
    assert len(first) == 64


def test_preview_token_changes_with_result():
    route = sample_route()
    trip = sample_trip()

    optimized = nearest_neighbour_sequence(
        sample_stops(),
        sample_orders(),
        sample_vehicle(),
    )

    first = preview_token(
        route, trip, sample_orders(),
        sample_vehicle(), optimized,
        measurement(distance=10000),
    )

    second = preview_token(
        route, trip, sample_orders(),
        sample_vehicle(), optimized,
        measurement(distance=11000),
    )

    assert first != second


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER],
)
def test_staff_can_view_saved_sequence(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.stop_sequencing_controller."
            "get_saved_sequence",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_preview().model_copy(
                update={
                    "is_applied": True,
                    "can_apply": False,
                    "preview_token": None,
                }
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                result = await http.get(URL)

        assert result.status_code == 200
        assert result.json()["is_applied"] is True

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DRIVER],
)
def test_nonstaff_cannot_view_sequence(role):
    async def run():
        app = make_app(role)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http:
            result = await http.get(URL)

        assert result.status_code == 403

    asyncio.run(run())


def test_unauthenticated_user_rejected():
    async def run():
        app = make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http:
            result = await http.get(URL)

        assert result.status_code == 401

    asyncio.run(run())


def test_dispatcher_can_preview():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.stop_sequencing_controller."
            "preview_sequence",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_preview()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                result = await http.post(
                    f"{URL}/preview"
                )

        assert result.status_code == 200
        assert result.json()["can_apply"] is True

    asyncio.run(run())


def test_dispatcher_can_apply():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.stop_sequencing_controller."
            "apply_sequence",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.return_value = sample_preview().model_copy(
                update={
                    "is_applied": True,
                    "can_apply": False,
                    "preview_token": None,
                }
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                result = await http.post(
                    f"{URL}/apply",
                    json={"preview_token": "a" * 64},
                )

        assert result.status_code == 200
        mocked.assert_awaited_once_with(
            TRIP_ID, "a" * 64
        )

    asyncio.run(run())


def test_admin_cannot_apply():
    async def run():
        app = make_app(Role.ADMIN)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as http:
            result = await http.post(
                f"{URL}/apply",
                json={"preview_token": "a" * 64},
            )

        assert result.status_code == 403

    asyncio.run(run())


def test_apply_requires_csrf():
    async def run():
        app = make_app(
            Role.DISPATCHER,
            skip_csrf=False,
        )

        with patch(
            "app.controllers.stop_sequencing_controller."
            "apply_sequence",
            new_callable=AsyncMock,
        ) as mocked:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                result = await http.post(
                    f"{URL}/apply",
                    json={"preview_token": "a" * 64},
                )

        assert result.status_code == 403
        mocked.assert_not_awaited()

    asyncio.run(run())


def test_dispatch_conflict_returns_409():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.stop_sequencing_controller."
            "preview_sequence",
            new_callable=AsyncMock,
        ) as mocked:
            mocked.side_effect = SequenceConflictError(
                "Already optimized."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as http:
                result = await http.post(
                    f"{URL}/preview"
                )

        assert result.status_code == 409

    asyncio.run(run())
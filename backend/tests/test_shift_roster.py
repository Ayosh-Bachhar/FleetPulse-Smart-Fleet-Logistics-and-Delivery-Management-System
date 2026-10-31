import asyncio

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.controllers.shift_roster_controller import (
    router as shift_router,
)
from app.core.access_control import (
    get_current_user,
    require_csrf,
)

from app.models.user import Role
from app.models.shift import Shift, ShiftStatus

from app.schemas.shift_roster_schemas import (
    ShiftCreate,
    ShiftUpdate,
    ShiftResponse,
    ShiftListResponse,
    HolidayCheckResponse,
)

from app.services.shift_roster_service import (
    ShiftConflictError,
    ShiftNotFoundError,
    intervals_overlap,
    local_shift_dates,
    normalize_period,
    validate_shift_resources,
)

from app.integrations.calendarific_holidays_client import (
    get_holidays_for_year,
)


URL = "/api/v1/shifts"

DRIVER_ID = "507f1f77bcf86cd799439011"
VEHICLE_ID = "507f1f77bcf86cd799439012"
SHIFT_ID = "507f1f77bcf86cd799439013"


def shift_data():
    return {
        "driver_id": DRIVER_ID,
        "vehicle_id": VEHICLE_ID,
        "start_at": "2030-12-16T09:00:00+06:00",
        "end_at": "2030-12-16T17:00:00+06:00",
    }


def sample_response():
    start = datetime(
        2030, 12, 16, 3, 0,
        tzinfo=timezone.utc,
    )

    return ShiftResponse(
        id=SHIFT_ID,
        driver_id=DRIVER_ID,
        driver_name="Test Driver",
        vehicle_id=VEHICLE_ID,
        vehicle_registration="FP-DEMO-001",
        vehicle_type="Truck",
        start_at=start,
        end_at=start + timedelta(hours=8),
        status=ShiftStatus.SCHEDULED,
        holiday_names=[],
        holiday_source="sample",
        holiday_notice="Sample calendar only.",
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


def make_app(role=None, bypass_csrf=True):
    app = FastAPI()
    app.include_router(shift_router, prefix="/api/v1")

    if role is not None:
        app.dependency_overrides[get_current_user] = (
            lambda: SimpleNamespace(role=role)
        )

    if bypass_csrf:
        app.dependency_overrides[require_csrf] = lambda: None

    return app


def test_shift_model_construct_without_database():
    start = datetime.now(timezone.utc)

    shift = Shift.model_construct(
        driver_id=DRIVER_ID,
        vehicle_id=VEHICLE_ID,
        start_at=start,
        end_at=start + timedelta(hours=8),
        status=ShiftStatus.SCHEDULED,
    )

    assert shift.status == ShiftStatus.SCHEDULED
    assert shift.holiday_names == []


def test_valid_shift_schema():
    data = ShiftCreate(**shift_data())

    assert data.driver_id == DRIVER_ID
    assert data.vehicle_id == VEHICLE_ID


def test_invalid_shift_periods():
    values = shift_data()

    with pytest.raises(ValidationError):
        ShiftCreate(
            **{
                **values,
                "end_at": values["start_at"],
            }
        )

    with pytest.raises(ValidationError):
        ShiftCreate(
            **{
                **values,
                "end_at": "2030-12-17T12:00:00+06:00",
            }
        )


def test_timezone_is_required():
    with pytest.raises(ValidationError):
        ShiftCreate(
            **{
                **shift_data(),
                "start_at": "2030-12-16T09:00",
            }
        )


def test_invalid_ids_rejected():
    with pytest.raises(ValidationError):
        ShiftCreate(
            **{
                **shift_data(),
                "driver_id": "invalid",
            }
        )


def test_empty_update_rejected():
    with pytest.raises(ValidationError):
        ShiftUpdate()

    with pytest.raises(ValidationError):
        ShiftUpdate(driver_id=None)


def test_overlap_rejected_but_adjacent_allowed():
    start = datetime(
        2030, 1, 1, 9,
        tzinfo=timezone.utc,
    )

    end = start + timedelta(hours=8)

    assert intervals_overlap(
        start,
        end,
        start + timedelta(hours=2),
        end + timedelta(hours=2),
    )

    assert not intervals_overlap(
        start,
        end,
        end,
        end + timedelta(hours=8),
    )


def test_bangladesh_local_holiday_dates():
    start = datetime(
        2026, 12, 16, 2,
        tzinfo=timezone.utc,
    )

    end = start + timedelta(hours=8)

    assert [
        day.isoformat()
        for day in local_shift_dates(start, end)
    ] == ["2026-12-16"]


def test_period_normalizes_to_utc():
    local_timezone = timezone(timedelta(hours=6))

    start = datetime(
        2030, 1, 1, 9,
        tzinfo=local_timezone,
    )

    end = start + timedelta(hours=8)

    result_start, result_end = normalize_period(
        start,
        end,
    )

    assert result_start.hour == 3
    assert result_start.tzinfo == timezone.utc
    assert result_end > result_start


def test_calendarific_sample_fallback():
    async def run():
        with patch(
            "app.integrations.calendarific_holidays_client."
            "get_cached_payload",
            new_callable=AsyncMock,
        ) as cache:

            cache.return_value = None

            with patch(
                "app.integrations.calendarific_holidays_client."
                "settings.CALENDARIFIC_API_KEY",
                "",
            ):
                holidays, source = await get_holidays_for_year(
                    2026
                )

            assert source == "sample"
            assert any(
                item["date"] == "2026-12-16"
                for item in holidays
            )

    asyncio.run(run())


def test_driver_vehicle_eligibility_rejected():
    async def run():
        driver = SimpleNamespace(
            status="available",
            license_class="light",
            license_expiry=datetime(
                2035, 1, 1
            ).date(),
            user_id=None,
        )

        vehicle = SimpleNamespace(
            status="available",
            vehicle_type="Truck",
        )

        with (
            patch(
                "app.services.shift_roster_service.Driver.get",
                new_callable=AsyncMock,
            ) as driver_get,
            patch(
                "app.services.shift_roster_service.Vehicle.get",
                new_callable=AsyncMock,
            ) as vehicle_get,
        ):
            driver_get.return_value = driver
            vehicle_get.return_value = vehicle

            from app.services.shift_roster_service import (
                ShiftResourceError,
            )

            with pytest.raises(
                ShiftResourceError,
                match="license class",
            ):
                await validate_shift_resources(
                    DRIVER_ID,
                    VEHICLE_ID,
                    datetime(
                        2030, 1, 1,
                        tzinfo=timezone.utc,
                    ),
                )

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.ADMIN, Role.DISPATCHER],
)
def test_staff_can_list_shifts(role):
    async def run():
        app = make_app(role)

        with patch(
            "app.controllers.shift_roster_controller.list_shifts",
            new_callable=AsyncMock,
        ) as mocked:

            mocked.return_value = ShiftListResponse(
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
            mocked.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "role",
    [Role.CUSTOMER, Role.DRIVER],
)
def test_non_staff_cannot_access_shifts(role):
    async def run():
        app = make_app(role)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 403

    asyncio.run(run())


def test_unauthenticated_access_rejected():
    async def run():
        app = make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(URL)

        assert response.status_code == 401

    asyncio.run(run())


def test_staff_can_create_shift():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.shift_roster_controller.create_shift",
            new_callable=AsyncMock,
        ) as mocked:

            mocked.return_value = sample_response()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=shift_data(),
                )

            assert response.status_code == 201
            assert response.json()["status"] == "scheduled"
            mocked.assert_awaited_once()

    asyncio.run(run())


def test_shift_overlap_returns_409():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.shift_roster_controller.create_shift",
            new_callable=AsyncMock,
        ) as mocked:

            mocked.side_effect = ShiftConflictError(
                "Overlapping shift."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=shift_data(),
                )

            assert response.status_code == 409

    asyncio.run(run())


def test_missing_shift_returns_404():
    async def run():
        app = make_app(Role.DISPATCHER)

        with patch(
            "app.controllers.shift_roster_controller.get_shift",
            new_callable=AsyncMock,
        ) as mocked:

            mocked.side_effect = ShiftNotFoundError(
                "Shift not found."
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    f"{URL}/{SHIFT_ID}"
                )

            assert response.status_code == 404

    asyncio.run(run())


def test_staff_can_update_shift():
    async def run():
        app = make_app(Role.DISPATCHER)

        updated = sample_response().model_copy(
            update={
                "status": ShiftStatus.CANCELLED,
            }
        )

        with patch(
            "app.controllers.shift_roster_controller.update_shift",
            new_callable=AsyncMock,
        ) as mocked:

            mocked.return_value = updated

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.patch(
                    f"{URL}/{SHIFT_ID}",
                    json={"status": "cancelled"},
                )

            assert response.status_code == 200
            assert response.json()["status"] == "cancelled"

    asyncio.run(run())


def test_holiday_preview_endpoint():
    async def run():
        app = make_app(Role.ADMIN)

        with patch(
            "app.controllers.shift_roster_controller."
            "check_shift_holidays",
            new_callable=AsyncMock,
        ) as mocked:

            mocked.return_value = HolidayCheckResponse(
                is_holiday=True,
                holiday_names=[
                    "2026-12-16: Victory Day"
                ],
                source="sample",
                notice="Public holiday warning.",
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    f"{URL}/holiday-check",
                    params={
                        "start_at": (
                            "2026-12-16T09:00:00+06:00"
                        ),
                        "end_at": (
                            "2026-12-16T17:00:00+06:00"
                        ),
                    },
                )

            assert response.status_code == 200
            assert response.json()["is_holiday"]

    asyncio.run(run())


def test_shift_write_requires_csrf():
    async def run():
        app = make_app(
            Role.ADMIN,
            bypass_csrf=False,
        )

        with patch(
            "app.controllers.shift_roster_controller.create_shift",
            new_callable=AsyncMock,
        ) as mocked:

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    URL,
                    json=shift_data(),
                )

            assert response.status_code == 403
            mocked.assert_not_awaited()

    asyncio.run(run())
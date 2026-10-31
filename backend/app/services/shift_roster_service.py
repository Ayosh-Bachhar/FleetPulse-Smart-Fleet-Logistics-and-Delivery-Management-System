import asyncio

from datetime import datetime, timedelta, timezone
from bson import ObjectId

from app.models.shift import Shift, ShiftStatus
from app.models.driver import Driver, DriverStatus
from app.models.vehicle import (
    Vehicle,
    VehicleStatus,
    is_vehicle_dispatchable,
)
from app.models.user import User, Role

from app.schemas.shift_roster_schemas import (
    ShiftCreate,
    ShiftUpdate,
    ShiftResponse,
    ShiftListResponse,
    HolidayCheckResponse,
    validate_shift_period,
)

from app.integrations.api_cache_helper import utc_datetime
from app.integrations.calendarific_holidays_client import (
    get_holidays_for_year,
)

from app.services.driver_management_service import (
    is_license_compatible,
)


# Bangladesh local time, UTC+06:00.
BANGLADESH_TIMEZONE = timezone(timedelta(hours=6))

# Prevent overlapping writes inside one FastAPI process.
# Cross-process concurrency must be addressed at F11 integration.
_shift_write_lock = asyncio.Lock()


class ShiftNotFoundError(Exception):
    pass


class ShiftResourceError(Exception):
    pass


class ShiftConflictError(Exception):
    pass


class ShiftTransitionError(Exception):
    pass


def intervals_overlap(start_a, end_a, start_b, end_b):
    """
    Time intervals use [start, end).
    Adjacent shifts are allowed.
    """
    return (
        utc_datetime(start_a) < utc_datetime(end_b)
        and utc_datetime(end_a) > utc_datetime(start_b)
    )


def normalize_period(start_at, end_at):
    start_at = utc_datetime(start_at)
    end_at = utc_datetime(end_at)

    validate_shift_period(start_at, end_at)

    return start_at, end_at


def local_shift_dates(start_at, end_at):
    start_local = start_at.astimezone(BANGLADESH_TIMEZONE)

    # End is exclusive; a shift ending exactly at midnight
    # does not include the next calendar day.
    last_included = end_at - timedelta(microseconds=1)
    end_local = last_included.astimezone(
        BANGLADESH_TIMEZONE
    )

    current = start_local.date()
    last_date = end_local.date()

    dates = []

    while current <= last_date:
        dates.append(current)
        current += timedelta(days=1)

    return dates


def holiday_notice(holiday_names, source):
    if holiday_names:
        return (
            "Public holiday warning: "
            + ", ".join(holiday_names)
            + ". Scheduling is allowed, but review the shift."
        )

    if source in ("sample", "mixed", "unavailable"):
        return (
            "Holiday information is incomplete. "
            "Only sample dates may be available."
        )

    if source == "stale-cache":
        return (
            "No holiday found in the last cached calendar. "
            "The information may be outdated."
        )

    return "No national holiday found for this shift."


async def check_shift_holidays(start_at, end_at):
    start_at, end_at = normalize_period(
        start_at,
        end_at,
    )

    dates = local_shift_dates(start_at, end_at)

    holiday_names = []
    sources = set()

    holiday_data = {}

    for year in sorted({day.year for day in dates}):
        holidays, source = await get_holidays_for_year(year)

        holiday_data[year] = holidays
        sources.add(source)

    for day in dates:
        for holiday in holiday_data[day.year]:
            if holiday.get("date") == day.isoformat():
                label = (
                    f"{day.isoformat()}: "
                    f"{holiday.get('name', 'Public holiday')}"
                )

                if label not in holiday_names:
                    holiday_names.append(label)

    source = (
        next(iter(sources))
        if len(sources) == 1
        else "mixed"
    )

    return HolidayCheckResponse(
        is_holiday=bool(holiday_names),
        holiday_names=holiday_names,
        source=source,
        notice=holiday_notice(holiday_names, source),
    )


async def get_shift_document(shift_id):
    if not ObjectId.is_valid(shift_id):
        raise ShiftNotFoundError("Shift not found.")

    shift = await Shift.get(ObjectId(shift_id))

    if shift is None:
        raise ShiftNotFoundError("Shift not found.")

    return shift


async def validate_shift_resources(
    driver_id,
    vehicle_id,
    end_at,
):
    driver = await Driver.get(ObjectId(driver_id))
    vehicle = await Vehicle.get(ObjectId(vehicle_id))

    if driver is None:
        raise ShiftResourceError("Selected driver does not exist.")

    if vehicle is None:
        raise ShiftResourceError("Selected vehicle does not exist.")

    if driver.status != DriverStatus.AVAILABLE:
        raise ShiftResourceError(
            "Selected driver is not available."
        )

    if not is_vehicle_dispatchable(vehicle):
        raise ShiftResourceError(
            "Selected vehicle is unavailable "
            "or requires maintenance."
        )

    if not is_license_compatible(
        driver.license_class,
        vehicle.vehicle_type,
    ):
        raise ShiftResourceError(
            "Driver license class does not permit "
            "the selected vehicle type."
        )

    shift_end_date = end_at.astimezone(
        BANGLADESH_TIMEZONE
    ).date()

    if driver.license_expiry < shift_end_date:
        raise ShiftResourceError(
            "Driver license expires before the shift ends."
        )

    if driver.user_id is not None:
        user = await User.get(driver.user_id)

        if (
            user is None
            or not user.is_active
            or user.role != Role.DRIVER
        ):
            raise ShiftResourceError(
                "Linked driver account is not active "
                "or does not have the Driver role."
            )

    return driver, vehicle


async def find_overlapping_shift(
    driver_id,
    vehicle_id,
    start_at,
    end_at,
    exclude_shift_id=None,
):
    filters = [
        {"status": ShiftStatus.SCHEDULED.value},
        {"start_at": {"$lt": end_at}},
        {"end_at": {"$gt": start_at}},
        {
            "$or": [
                {"driver_id": ObjectId(driver_id)},
                {"vehicle_id": ObjectId(vehicle_id)},
            ]
        },
    ]

    if exclude_shift_id:
        filters.append({
            "_id": {"$ne": ObjectId(exclude_shift_id)}
        })

    return await Shift.find({
        "$and": filters
    }).first_or_none()


async def shift_to_response(shift):
    driver = await Driver.get(shift.driver_id)
    vehicle = await Vehicle.get(shift.vehicle_id)

    start_at = utc_datetime(shift.start_at)
    end_at = utc_datetime(shift.end_at)

    return ShiftResponse(
        id=str(shift.id),
        driver_id=str(shift.driver_id),
        driver_name=(
            driver.full_name
            if driver is not None
            else "Unknown driver"
        ),
        vehicle_id=str(shift.vehicle_id),
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
        start_at=start_at,
        end_at=end_at,
        status=shift.status,
        holiday_names=shift.holiday_names,
        holiday_source=shift.holiday_source,
        holiday_notice=holiday_notice(
            shift.holiday_names,
            shift.holiday_source,
        ),
        created_at=utc_datetime(shift.created_at),
        updated_at=(
            utc_datetime(shift.updated_at)
            if shift.updated_at is not None
            else None
        ),
    )


async def create_shift(data: ShiftCreate):
    start_at, end_at = normalize_period(
        data.start_at,
        data.end_at,
    )

    async with _shift_write_lock:
        await validate_shift_resources(
            data.driver_id,
            data.vehicle_id,
            end_at,
        )

        existing = await find_overlapping_shift(
            data.driver_id,
            data.vehicle_id,
            start_at,
            end_at,
        )

        if existing is not None:
            raise ShiftConflictError(
                "The selected driver or vehicle already "
                "has an overlapping scheduled shift."
            )

        holiday = await check_shift_holidays(
            start_at,
            end_at,
        )

        shift = Shift(
            driver_id=ObjectId(data.driver_id),
            vehicle_id=ObjectId(data.vehicle_id),
            start_at=start_at,
            end_at=end_at,
            status=ShiftStatus.SCHEDULED,
            holiday_names=holiday.holiday_names,
            holiday_source=holiday.source,
        )

        await shift.insert()

    return await shift_to_response(shift)


async def get_shift(shift_id):
    shift = await get_shift_document(shift_id)
    return await shift_to_response(shift)


async def list_shifts(
    shift_status=None,
    driver_id=None,
    vehicle_id=None,
    page=1,
    page_size=10,
):
    filters = []

    if shift_status is not None:
        filters.append({
            "status": shift_status.value
        })

    if driver_id:
        filters.append({
            "driver_id": ObjectId(driver_id)
        })

    if vehicle_id:
        filters.append({
            "vehicle_id": ObjectId(vehicle_id)
        })

    query = Shift.find(*filters)

    total = await query.count()

    shifts = await (
        query.sort("-start_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    return ShiftListResponse(
        items=[
            await shift_to_response(shift)
            for shift in shifts
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_shift(shift_id, data: ShiftUpdate):
    async with _shift_write_lock:
        shift = await get_shift_document(shift_id)

        if shift.status != ShiftStatus.SCHEDULED:
            raise ShiftTransitionError(
                "Completed or cancelled shifts cannot be edited."
            )

        changes = data.model_dump(exclude_unset=True)

        requested_status = changes.get(
            "status",
            ShiftStatus.SCHEDULED,
        )

        # Completing/cancelling releases the resource reservation.
        if requested_status in (
            ShiftStatus.COMPLETED,
            ShiftStatus.CANCELLED,
        ):
            if set(changes.keys()) != {"status"}:
                raise ShiftTransitionError(
                    "Change the shift status separately "
                    "from scheduling details."
                )

            shift.status = requested_status
            shift.updated_at = datetime.now(timezone.utc)

            await shift.save()
            return await shift_to_response(shift)

        driver_id = changes.get(
            "driver_id",
            str(shift.driver_id),
        )

        vehicle_id = changes.get(
            "vehicle_id",
            str(shift.vehicle_id),
        )

        start_at = changes.get(
            "start_at",
            shift.start_at,
        )

        end_at = changes.get(
            "end_at",
            shift.end_at,
        )

        start_at, end_at = normalize_period(
            start_at,
            end_at,
        )

        await validate_shift_resources(
            driver_id,
            vehicle_id,
            end_at,
        )

        conflict = await find_overlapping_shift(
            driver_id,
            vehicle_id,
            start_at,
            end_at,
            exclude_shift_id=str(shift.id),
        )

        if conflict is not None:
            raise ShiftConflictError(
                "The updated shift overlaps another "
                "scheduled assignment."
            )

        holiday = await check_shift_holidays(
            start_at,
            end_at,
        )

        shift.driver_id = ObjectId(driver_id)
        shift.vehicle_id = ObjectId(vehicle_id)
        shift.start_at = start_at
        shift.end_at = end_at

        shift.holiday_names = holiday.holiday_names
        shift.holiday_source = holiday.source

        shift.updated_at = datetime.now(timezone.utc)

        await shift.save()

    return await shift_to_response(shift)
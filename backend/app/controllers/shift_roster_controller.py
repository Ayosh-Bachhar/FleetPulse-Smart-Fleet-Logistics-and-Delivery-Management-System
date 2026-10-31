from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from pydantic import AwareDatetime

from app.core.access_control import (
    require_roles,
    require_csrf,
)

from app.models.user import Role
from app.models.shift import ShiftStatus

from app.schemas.shift_roster_schemas import (
    ShiftCreate,
    ShiftUpdate,
    ShiftResponse,
    ShiftListResponse,
    HolidayCheckResponse,
)

from app.services.shift_roster_service import (
    ShiftNotFoundError,
    ShiftResourceError,
    ShiftConflictError,
    ShiftTransitionError,
    create_shift,
    get_shift,
    list_shifts,
    update_shift,
    check_shift_holidays,
)


router = APIRouter(
    prefix="/shifts",
    tags=["Shift Roster"],
    dependencies=[
        Depends(require_roles(Role.ADMIN, Role.DISPATCHER))
    ],
)


@router.post(
    "",
    response_model=ShiftResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_shift_endpoint(data: ShiftCreate):
    try:
        return await create_shift(data)

    except ShiftResourceError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except ShiftConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=ShiftListResponse,
)
async def list_shifts_endpoint(
    shift_status: ShiftStatus | None = Query(
        default=None,
        alias="status",
    ),
    driver_id: str | None = None,
    vehicle_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    for value in (driver_id, vehicle_id):
        if value and not ObjectId.is_valid(value):
            raise HTTPException(
                status_code=422,
                detail="Invalid driver or vehicle ID.",
            )

    return await list_shifts(
        shift_status=shift_status,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/holiday-check",
    response_model=HolidayCheckResponse,
)
async def check_holidays_endpoint(
    start_at: AwareDatetime,
    end_at: AwareDatetime,
):
    from app.schemas.shift_roster_schemas import (
        validate_shift_period,
    )

    try:
        validate_shift_period(start_at, end_at)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return await check_shift_holidays(
        start_at,
        end_at,
    )


@router.get(
    "/{shift_id}",
    response_model=ShiftResponse,
)
async def get_shift_endpoint(shift_id: str):
    try:
        return await get_shift(shift_id)

    except ShiftNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{shift_id}",
    response_model=ShiftResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_shift_endpoint(
    shift_id: str,
    data: ShiftUpdate,
):
    try:
        return await update_shift(shift_id, data)

    except ShiftNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ShiftResourceError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except (
        ShiftConflictError,
        ShiftTransitionError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
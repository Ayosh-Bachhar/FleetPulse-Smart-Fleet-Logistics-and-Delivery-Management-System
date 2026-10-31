from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.core.access_control import (
    require_roles,
    require_csrf,
    get_current_user,
)
from app.models.user import User, Role
from app.models.trip import TripStatus

from app.schemas.dispatch_planning_schemas import (
    DispatchRequest,
    CompleteTripRequest,
    DispatchOrderListResponse,
    TripResponse,
    TripListResponse,
)

from app.services.dispatch_planning_service import (
    DispatchNotFoundError,
    DispatchValidationError,
    DispatchConflictError,
    list_ready_orders,
    list_trips,
    get_trip,
    dispatch_trip,
    complete_trip,
    cancel_trip,
)


router = APIRouter(
    prefix="/trips",
    tags=["Dispatch Planning"],
    dependencies=[
        Depends(require_roles(Role.ADMIN, Role.DISPATCHER))
    ],
)


def handle_dispatch_error(exc):
    if isinstance(exc, DispatchNotFoundError):
        return HTTPException(
            status_code=404,
            detail=str(exc),
        )

    if isinstance(exc, DispatchConflictError):
        return HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return HTTPException(
        status_code=422,
        detail=str(exc),
    )


@router.get(
    "/eligible-orders",
    response_model=DispatchOrderListResponse,
)
async def eligible_orders_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=100,
        ge=1,
        le=100,
    ),
):
    return await list_ready_orders(
        page=page,
        page_size=page_size,
    )


@router.get(
    "",
    response_model=TripListResponse,
)
async def list_trips_endpoint(
    trip_status: TripStatus | None = Query(
        default=None,
        alias="status",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
):
    return await list_trips(
        trip_status=trip_status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=TripResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def dispatch_trip_endpoint(
    data: DispatchRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return await dispatch_trip(
            data,
            str(current_user.id),
        )
    except (
        DispatchNotFoundError,
        DispatchValidationError,
        DispatchConflictError,
    ) as exc:
        raise handle_dispatch_error(exc) from exc


@router.get(
    "/{trip_id}",
    response_model=TripResponse,
)
async def get_trip_endpoint(trip_id: str):
    try:
        return await get_trip(trip_id)
    except DispatchNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{trip_id}/complete",
    response_model=TripResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def complete_trip_endpoint(
    trip_id: str,
    data: CompleteTripRequest,
):
    try:
        return await complete_trip(
            trip_id,
            data.actual_distance_km,
        )
    except (
        DispatchNotFoundError,
        DispatchConflictError,
    ) as exc:
        raise handle_dispatch_error(exc) from exc


@router.post(
    "/{trip_id}/cancel",
    response_model=TripResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def cancel_trip_endpoint(trip_id: str):
    try:
        return await cancel_trip(trip_id)
    except (
        DispatchNotFoundError,
        DispatchConflictError,
    ) as exc:
        raise handle_dispatch_error(exc) from exc
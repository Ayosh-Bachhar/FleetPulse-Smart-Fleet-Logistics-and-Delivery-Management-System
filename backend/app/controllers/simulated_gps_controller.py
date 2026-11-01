from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from app.core.access_control import (
    get_current_user,
    require_roles,
    require_csrf,
)
from app.models.user import User, Role

from app.schemas.simulated_gps_schemas import (
    StartSimulationRequest,
    GPSTripListResponse,
    GPSPositionResponse,
)

from app.services.simulated_gps_service import (
    GPSNotFoundError,
    GPSForbiddenError,
    GPSConflictError,
    GPSValidationError,
    list_gps_trips,
    get_gps_position,
    start_simulation,
    pause_simulation,
    reset_simulation,
)


router = APIRouter(
    prefix="/gps",
    tags=["Simulated GPS"],
    dependencies=[
        Depends(
            require_roles(
                Role.ADMIN,
                Role.DISPATCHER,
                Role.DRIVER,
            )
        ),
    ],
)


GPS_ERRORS = (
    GPSNotFoundError,
    GPSForbiddenError,
    GPSConflictError,
    GPSValidationError,
)


def gps_http_error(exc):
    if isinstance(exc, GPSNotFoundError):
        code = 404

    elif isinstance(exc, GPSForbiddenError):
        code = 403

    elif isinstance(exc, GPSConflictError):
        code = 409

    else:
        code = 422

    return HTTPException(
        status_code=code,
        detail=str(exc),
    )


@router.get(
    "/trips",
    response_model=GPSTripListResponse,
)
async def list_gps_trips_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=100,
        ge=1,
        le=100,
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    return await list_gps_trips(
        current_user,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/trips/{trip_id}",
    response_model=GPSPositionResponse,
)
async def get_gps_position_endpoint(
    trip_id: str,
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        return await get_gps_position(
            trip_id,
            current_user,
        )

    except GPS_ERRORS as exc:
        raise gps_http_error(exc) from exc


@router.post(
    "/trips/{trip_id}/start",
    response_model=GPSPositionResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def start_simulation_endpoint(
    trip_id: str,
    data: StartSimulationRequest,
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        return await start_simulation(
            trip_id,
            current_user,
            data.speed_kmh,
        )

    except GPS_ERRORS as exc:
        raise gps_http_error(exc) from exc


@router.post(
    "/trips/{trip_id}/pause",
    response_model=GPSPositionResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def pause_simulation_endpoint(
    trip_id: str,
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        return await pause_simulation(
            trip_id,
            current_user,
        )

    except GPS_ERRORS as exc:
        raise gps_http_error(exc) from exc


@router.post(
    "/trips/{trip_id}/reset",
    response_model=GPSPositionResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def reset_simulation_endpoint(
    trip_id: str,
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        return await reset_simulation(
            trip_id,
            current_user,
        )

    except GPS_ERRORS as exc:
        raise gps_http_error(exc) from exc
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from app.core.access_control import (
    require_roles,
    require_csrf,
)
from app.models.user import Role

from app.schemas.route_distance_and_time_schemas import (
    TripRouteResponse,
    RouteStatusResponse,
)

from app.services.route_distance_and_time_service import (
    RouteTripNotFoundError,
    RouteNotFoundError,
    RouteValidationError,
    RouteConflictError,
    RouteUnavailableError,
    get_route,
    get_route_status,
    calculate_trip_route,
)


router = APIRouter(
    prefix="/trips",
    tags=["Route Distance and Time"],
    dependencies=[
        Depends(require_roles(Role.ADMIN, Role.DISPATCHER))
    ],
)


def route_http_error(exc):
    if isinstance(
        exc,
        (RouteTripNotFoundError, RouteNotFoundError),
    ):
        return HTTPException(
            status_code=404,
            detail=str(exc),
        )

    if isinstance(exc, RouteConflictError):
        return HTTPException(
            status_code=409,
            detail=str(exc),
        )

    if isinstance(exc, RouteUnavailableError):
        return HTTPException(
            status_code=503,
            detail=str(exc),
        )

    return HTTPException(
        status_code=422,
        detail=str(exc),
    )


ROUTE_ERRORS = (
    RouteTripNotFoundError,
    RouteNotFoundError,
    RouteValidationError,
    RouteConflictError,
    RouteUnavailableError,
)


@router.get(
    "/{trip_id}/route/status",
    response_model=RouteStatusResponse,
)
async def route_status_endpoint(trip_id: str):
    try:
        return await get_route_status(trip_id)
    except ROUTE_ERRORS as exc:
        raise route_http_error(exc) from exc


@router.get(
    "/{trip_id}/route",
    response_model=TripRouteResponse,
)
async def get_route_endpoint(trip_id: str):
    try:
        return await get_route(trip_id)
    except ROUTE_ERRORS as exc:
        raise route_http_error(exc) from exc


@router.post(
    "/{trip_id}/route",
    response_model=TripRouteResponse,
    dependencies=[
        Depends(require_roles(Role.DISPATCHER)),
        Depends(require_csrf),
    ],
)
async def calculate_route_endpoint(
    trip_id: str,
    refresh: bool = Query(default=False),
):
    try:
        return await calculate_trip_route(
            trip_id,
            force_refresh=refresh,
        )
    except ROUTE_ERRORS as exc:
        raise route_http_error(exc) from exc
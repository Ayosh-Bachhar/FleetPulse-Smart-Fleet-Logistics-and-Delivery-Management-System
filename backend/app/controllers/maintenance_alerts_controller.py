from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.core.access_control import (
    get_current_user,
    require_roles,
    require_csrf,
)

from app.models.user import Role, User

from app.schemas.maintenance_alerts_schemas import (
    AddMileageRequest,
    CompleteServiceRequest,
    ChangeServiceIntervalRequest,
    MaintenanceVehicleResponse,
    MaintenanceListResponse,
    MaintenanceHistoryResponse,
)

from app.services.maintenance_alerts_service import (
    MaintenanceVehicleNotFoundError,
    MaintenanceOperationError,
    list_maintenance,
    get_maintenance,
    get_maintenance_history,
    add_vehicle_distance,
    change_service_interval,
    complete_vehicle_service,
)


router = APIRouter(
    prefix="/maintenance",
    tags=["Maintenance Alerts"],
    dependencies=[
        Depends(require_roles(Role.ADMIN, Role.DISPATCHER))
    ],
)


@router.get(
    "",
    response_model=MaintenanceListResponse,
)
async def list_maintenance_endpoint(
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
    only_attention: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
):
    return await list_maintenance(
        search=search,
        only_attention=only_attention,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{vehicle_id}",
    response_model=MaintenanceVehicleResponse,
)
async def get_maintenance_endpoint(vehicle_id: str):
    try:
        return await get_maintenance(vehicle_id)

    except MaintenanceVehicleNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/{vehicle_id}/history",
    response_model=MaintenanceHistoryResponse,
)
async def get_maintenance_history_endpoint(
    vehicle_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
):
    try:
        return await get_maintenance_history(
            vehicle_id,
            page=page,
            page_size=page_size,
        )

    except MaintenanceVehicleNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{vehicle_id}/distance",
    response_model=MaintenanceVehicleResponse,
    dependencies=[Depends(require_csrf)],
)
async def add_distance_endpoint(
    vehicle_id: str,
    data: AddMileageRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return await add_vehicle_distance(
            vehicle_id,
            data,
            current_user.id,
        )

    except MaintenanceVehicleNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{vehicle_id}/interval",
    response_model=MaintenanceVehicleResponse,
    dependencies=[Depends(require_csrf)],
)
async def change_interval_endpoint(
    vehicle_id: str,
    data: ChangeServiceIntervalRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return await change_service_interval(
            vehicle_id,
            data,
            current_user.id,
        )

    except MaintenanceVehicleNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{vehicle_id}/complete-service",
    response_model=MaintenanceVehicleResponse,
    dependencies=[Depends(require_csrf)],
)
async def complete_service_endpoint(
    vehicle_id: str,
    data: CompleteServiceRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return await complete_vehicle_service(
            vehicle_id,
            data,
            current_user.id,
        )

    except MaintenanceVehicleNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except MaintenanceOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
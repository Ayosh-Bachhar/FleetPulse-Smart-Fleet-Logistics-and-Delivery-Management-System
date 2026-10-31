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
)
from app.models.user import Role
from app.models.vehicle import VehicleStatus

from app.schemas.fleet_management_schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VehicleListResponse,
)

from app.services.fleet_management_service import (
    VehicleAlreadyExistsError,
    VehicleNotFoundError,
    VehicleMaintenanceBlockedError,
    create_vehicle,
    list_vehicles,
    get_vehicle,
    update_vehicle,
)


router = APIRouter(
    prefix="/vehicles",
    tags=["Fleet Management"],
    dependencies=[
        Depends(require_roles(Role.ADMIN, Role.DISPATCHER))
    ],
)


@router.post(
    "",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_vehicle_endpoint(data: VehicleCreate):
    try:
        return await create_vehicle(data)

    except VehicleAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=VehicleListResponse,
)
async def list_vehicles_endpoint(
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
    vehicle_status: VehicleStatus | None = Query(
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
    return await list_vehicles(
        search=search,
        vehicle_status=vehicle_status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
)
async def get_vehicle_endpoint(vehicle_id: str):
    try:
        return await get_vehicle(vehicle_id)

    except VehicleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_vehicle_endpoint(
    vehicle_id: str,
    data: VehicleUpdate,
):
    try:
        return await update_vehicle(vehicle_id, data)

    except VehicleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except VehicleAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except VehicleMaintenanceBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
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
from app.models.driver import (
    DriverLicenseClass,
    DriverStatus,
)

from app.schemas.driver_management_schemas import (
    DriverCreate,
    DriverUpdate,
    DriverResponse,
    DriverListResponse,
    DriverCompatibilityResponse,
)

from app.services.driver_management_service import (
    DriverAlreadyExistsError,
    DriverNotFoundError,
    DriverUserError,
    DriverVehicleNotFoundError,
    create_driver,
    list_drivers,
    get_driver,
    update_driver,
    check_driver_compatibility,
)


router = APIRouter(
    prefix="/drivers",
    tags=["Driver Management"],
    dependencies=[
        Depends(require_roles(Role.ADMIN, Role.DISPATCHER))
    ],
)


@router.post(
    "",
    response_model=DriverResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_driver_endpoint(data: DriverCreate):
    try:
        return await create_driver(data)

    except DriverAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except DriverUserError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=DriverListResponse,
)
async def list_drivers_endpoint(
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
    driver_status: DriverStatus | None = Query(
        default=None,
        alias="status",
    ),
    license_class: DriverLicenseClass | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
):
    return await list_drivers(
        search=search,
        driver_status=driver_status,
        license_class=license_class,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{driver_id}",
    response_model=DriverResponse,
)
async def get_driver_endpoint(driver_id: str):
    try:
        return await get_driver(driver_id)

    except DriverNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/{driver_id}/compatibility/{vehicle_id}",
    response_model=DriverCompatibilityResponse,
)
async def check_compatibility_endpoint(
    driver_id: str,
    vehicle_id: str,
):
    try:
        return await check_driver_compatibility(
            driver_id,
            vehicle_id,
        )

    except (
        DriverNotFoundError,
        DriverVehicleNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{driver_id}",
    response_model=DriverResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_driver_endpoint(
    driver_id: str,
    data: DriverUpdate,
):
    try:
        return await update_driver(driver_id, data)

    except DriverNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except DriverAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except DriverUserError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
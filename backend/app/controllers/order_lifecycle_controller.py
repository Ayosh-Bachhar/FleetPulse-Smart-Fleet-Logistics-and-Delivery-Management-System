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
from app.models.order import OrderStatus
from app.models.user import User, Role

from app.schemas.order_lifecycle_schemas import (
    OrderStatusChange,
    OrderLifecycleResponse,
    OrderLifecycleListResponse,
)

from app.services.order_lifecycle_service import (
    LifecycleNotFoundError,
    LifecyclePermissionError,
    LifecycleConflictError,
    list_order_lifecycle,
    get_order_lifecycle,
    change_order_status,
)


router = APIRouter(
    prefix="/order-lifecycle",
    tags=["Order Lifecycle"],
    dependencies=[
        Depends(require_roles(
            Role.ADMIN,
            Role.DISPATCHER,
            Role.DRIVER,
            Role.CUSTOMER,
        )),
    ],
)


LIFECYCLE_ERRORS = (
    LifecycleNotFoundError,
    LifecyclePermissionError,
    LifecycleConflictError,
)


def lifecycle_http_error(exc):
    if isinstance(exc, LifecycleNotFoundError):
        code = 404

    elif isinstance(exc, LifecyclePermissionError):
        code = 403

    else:
        code = 409

    return HTTPException(
        status_code=code,
        detail=str(exc),
    )


@router.get(
    "/orders",
    response_model=OrderLifecycleListResponse,
)
async def list_lifecycle_endpoint(
    order_status: OrderStatus | None = Query(
        default=None,
        alias="status",
    ),
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        return await list_order_lifecycle(
            current_user,
            order_status=order_status,
            search=search,
            page=page,
            page_size=page_size,
        )

    except LIFECYCLE_ERRORS as exc:
        raise lifecycle_http_error(exc) from exc


@router.get(
    "/orders/{order_id}",
    response_model=OrderLifecycleResponse,
)
async def get_lifecycle_endpoint(
    order_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_order_lifecycle(
            order_id,
            current_user,
        )

    except LIFECYCLE_ERRORS as exc:
        raise lifecycle_http_error(exc) from exc


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderLifecycleResponse,
    dependencies=[
        Depends(require_roles(
            Role.DISPATCHER,
            Role.DRIVER,
        )),
        Depends(require_csrf),
    ],
)
async def change_order_status_endpoint(
    order_id: str,
    data: OrderStatusChange,
    current_user: User = Depends(get_current_user),
):
    try:
        return await change_order_status(
            order_id,
            data.status,
            current_user,
        )

    except LIFECYCLE_ERRORS as exc:
        raise lifecycle_http_error(exc) from exc
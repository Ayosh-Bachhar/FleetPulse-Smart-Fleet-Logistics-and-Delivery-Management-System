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
from app.models.user import User, Role
from app.models.order import OrderStatus

from app.schemas.order_intake_schemas import (
    OrderCreate,
    OrderResponse,
    OrderListResponse,
)

from app.services.order_intake_service import (
    OrderNotFoundError,
    OrderValidationError,
    OrderPermissionError,
    OrderConflictError,
    create_order,
    list_orders,
    get_order,
)


router = APIRouter(
    prefix="/orders",
    tags=["Order Intake"],
    dependencies=[
        Depends(
            require_roles(
                Role.CUSTOMER,
                Role.DISPATCHER,
            )
        )
    ],
)


def order_http_error(exc):
    if isinstance(exc, OrderNotFoundError):
        code = 404
    elif isinstance(exc, OrderPermissionError):
        code = 403
    elif isinstance(exc, OrderConflictError):
        code = 409
    else:
        code = 422

    return HTTPException(
        status_code=code,
        detail=str(exc),
    )


ORDER_ERRORS = (
    OrderNotFoundError,
    OrderValidationError,
    OrderPermissionError,
    OrderConflictError,
)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_order_endpoint(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
):
    try:
        return await create_order(
            data,
            current_user,
        )

    except ORDER_ERRORS as exc:
        raise order_http_error(exc) from exc


@router.get(
    "",
    response_model=OrderListResponse,
)
async def list_orders_endpoint(
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
        return await list_orders(
            current_user,
            order_status=order_status,
            search=search,
            page=page,
            page_size=page_size,
        )

    except ORDER_ERRORS as exc:
        raise order_http_error(exc) from exc


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
)
async def get_order_endpoint(
    order_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_order(
            order_id,
            current_user,
        )

    except ORDER_ERRORS as exc:
        raise order_http_error(exc) from exc
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.order import OrderStatus


class OrderStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Delivered is reserved for F10 Delivery Proof.
    status: Literal[
        OrderStatus.WAREHOUSE,
        OrderStatus.OUT_FOR_DELIVERY,
    ]


class OrderLifecycleResponse(BaseModel):
    id: str
    reference_code: str

    pickup_address: str
    delivery_address: str

    status: OrderStatus
    trip_id: str | None

    is_rush: bool
    created_at: datetime
    updated_at: datetime | None

    # None means the current user has
    # no permitted next transition.
    allowed_next_status: OrderStatus | None


class OrderLifecycleListResponse(BaseModel):
    items: list[OrderLifecycleResponse]
    total: int
    page: int
    page_size: int
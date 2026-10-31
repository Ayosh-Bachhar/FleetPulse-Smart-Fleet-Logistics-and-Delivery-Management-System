from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class OrderStatus(str, Enum):
    PLACED = "placed"
    WAREHOUSE = "warehouse"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"


class Order(Document):
    reference_code: str = Field(
        default_factory=lambda: (
            "FP-" + uuid4().hex[:12].upper()
        )
    )

    customer_id: PydanticObjectId

    pickup_address: str = Field(
        min_length=5,
        max_length=500,
    )
    delivery_address: str = Field(
        min_length=5,
        max_length=500,
    )

    weight_kg: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    length_cm: float = Field(gt=0, allow_inf_nan=False)
    width_cm: float = Field(gt=0, allow_inf_nan=False)
    height_cm: float = Field(gt=0, allow_inf_nan=False)

    # Must match length * width * height / 1,000,000.
    volume_m3: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    is_rush: bool = False
    status: OrderStatus = OrderStatus.PLACED

    # F11 assignment. F9 controls order status transitions.
    trip_id: PydanticObjectId | None = None

    public_tracking_uuid: str = Field(
        default_factory=lambda: str(uuid4())
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime | None = None

    class Settings:
        name = "orders"

        indexes = [
            IndexModel(
                [("reference_code", ASCENDING)],
                unique=True,
                name="unique_order_reference",
            ),
            IndexModel(
                [("public_tracking_uuid", ASCENDING)],
                unique=True,
                name="unique_order_tracking_uuid",
            ),
            "customer_id",
            "status",
            "trip_id",
        ]
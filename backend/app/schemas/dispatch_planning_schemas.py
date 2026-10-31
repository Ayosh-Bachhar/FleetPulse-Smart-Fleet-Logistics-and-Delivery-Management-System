from datetime import datetime, timedelta

from bson import ObjectId
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.trip import TripStatus
from app.models.order import OrderStatus


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shift_id: str
    order_ids: list[str] = Field(
        min_length=1,
        max_length=20,
    )

    @field_validator("shift_id")
    @classmethod
    def validate_shift_id(cls, value):
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid shift ID.")
        return value

    @field_validator("order_ids")
    @classmethod
    def validate_order_ids(cls, values):
        if any(not ObjectId.is_valid(value) for value in values):
            raise ValueError("Invalid order ID.")

        if len(values) != len(set(values)):
            raise ValueError("Duplicate orders are not allowed.")

        return values


class CompleteTripRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_distance_km: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )


class DispatchOrderResponse(BaseModel):
    id: str
    reference_code: str
    weight_kg: float
    volume_m3: float
    pickup_address: str
    delivery_address: str
    is_rush: bool
    status: OrderStatus


class DispatchOrderListResponse(BaseModel):
    items: list[DispatchOrderResponse]
    total: int
    page: int
    page_size: int


class TripResponse(BaseModel):
    id: str

    order_ids: list[str]
    order_count: int
    order_references: list[str]

    driver_id: str
    driver_name: str

    vehicle_id: str
    vehicle_registration: str
    vehicle_type: str

    shift_id: str

    start_at: datetime
    end_at: datetime

    total_weight_kg: float
    total_volume_m3: float

    status: TripStatus

    estimated_distance_km: float | None
    actual_distance_km: float | None

    created_by: str

    created_at: datetime
    updated_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


class TripListResponse(BaseModel):
    items: list[TripResponse]
    total: int
    page: int
    page_size: int
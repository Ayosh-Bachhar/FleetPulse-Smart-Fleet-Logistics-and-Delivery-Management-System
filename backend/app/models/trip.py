from datetime import datetime, timezone
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class TripStatus(str, Enum):
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Trip(Document):
    order_ids: list[PydanticObjectId] = Field(
        min_length=1,
        max_length=20,
    )

    driver_id: PydanticObjectId
    vehicle_id: PydanticObjectId
    shift_id: PydanticObjectId

    start_at: datetime
    end_at: datetime

    total_weight_kg: float = Field(ge=0)
    total_volume_m3: float = Field(ge=0)

    status: TripStatus = TripStatus.DISPATCHED

    # Shared F5/F12 contract.
    estimated_distance_km: float | None = Field(
        default=None,
        ge=0,
    )
    actual_distance_km: float | None = Field(
        default=None,
        ge=0,
    )

    created_by: PydanticObjectId

    completed_at: datetime | None = None
    cancelled_at: datetime | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime | None = None

    class Settings:
        name = "trips"

        indexes = [
            IndexModel(
                [("driver_id", ASCENDING), ("start_at", ASCENDING)],
                name="trip_driver_schedule",
            ),
            IndexModel(
                [("vehicle_id", ASCENDING), ("start_at", ASCENDING)],
                name="trip_vehicle_schedule",
            ),
            IndexModel(
                [("order_ids", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "status": TripStatus.DISPATCHED.value
                },
                name="unique_active_trip_order",
            ),
        ]
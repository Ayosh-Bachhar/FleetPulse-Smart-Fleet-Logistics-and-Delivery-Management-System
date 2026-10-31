from datetime import datetime, timezone
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


class MaintenanceEvent(str, Enum):
    DISTANCE_ADDED = "distance_added"
    SERVICE_COMPLETED = "service_completed"
    INTERVAL_CHANGED = "interval_changed"


class MaintenanceRecord(Document):
    vehicle_id: PydanticObjectId
    actor_user_id: PydanticObjectId

    event_type: MaintenanceEvent

    distance_km: float = Field(
        default=0,
        ge=0,
        allow_inf_nan=False,
    )

    odometer_km: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    service_interval_km: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    maintenance_triggered: bool = False

    notes: str | None = Field(
        default=None,
        max_length=500,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "maintenance_records"

        indexes = [
            IndexModel(
                [
                    ("vehicle_id", ASCENDING),
                    ("created_at", DESCENDING),
                ],
                name="vehicle_maintenance_history",
            ),
        ]
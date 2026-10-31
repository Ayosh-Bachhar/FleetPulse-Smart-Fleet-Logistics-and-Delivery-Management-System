from datetime import datetime, timezone
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class ShiftStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Shift(Document):
    driver_id: PydanticObjectId
    vehicle_id: PydanticObjectId

    start_at: datetime
    end_at: datetime

    status: ShiftStatus = ShiftStatus.SCHEDULED

    holiday_names: list[str] = Field(default_factory=list)
    holiday_source: str = "unavailable"

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime | None = None

    class Settings:
        name = "shifts"
        indexes = [
            IndexModel(
                [
                    ("driver_id", ASCENDING),
                    ("start_at", ASCENDING),
                ],
                name="driver_shift_schedule",
            ),
            IndexModel(
                [
                    ("vehicle_id", ASCENDING),
                    ("start_at", ASCENDING),
                ],
                name="vehicle_shift_schedule",
            ),
        ]
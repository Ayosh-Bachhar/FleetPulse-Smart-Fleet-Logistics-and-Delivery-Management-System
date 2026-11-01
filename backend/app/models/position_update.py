from datetime import datetime, timezone
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class GPSStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    STOPPED = "stopped"


class PositionUpdate(Document):
    trip_id: PydanticObjectId

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    status: GPSStatus = GPSStatus.IDLE

    # Simulated movement, not real vehicle mileage.
    progress_m: float = Field(
        default=0,
        ge=0,
        allow_inf_nan=False,
    )

    speed_kmh: float = Field(
        default=30,
        gt=0,
        le=120,
        allow_inf_nan=False,
    )

    tick_count: int = Field(default=0, ge=0)

    # Detect changes to F12/F13 routing data.
    route_calculated_at: datetime

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "position_updates"

        indexes = [
            IndexModel(
                [("trip_id", ASCENDING)],
                unique=True,
                name="unique_gps_position_trip",
            ),
        ]
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class StartSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speed_kmh: float = Field(
        default=30,
        ge=5,
        le=120,
        allow_inf_nan=False,
    )


class GPSTripItem(BaseModel):
    id: str
    vehicle_registration: str
    driver_name: str
    order_count: int
    trip_status: str
    route_available: bool


class GPSTripListResponse(BaseModel):
    items: list[GPSTripItem]
    total: int
    page: int
    page_size: int


class GPSPositionResponse(BaseModel):
    trip_id: str
    vehicle_id: str

    latitude: float
    longitude: float

    status: Literal[
        "not_started",
        "idle",
        "running",
        "paused",
        "finished",
        "stopped",
    ]

    speed_kmh: float

    progress_percent: float = Field(ge=0, le=100)

    # F12's route distance, not recorded mileage.
    route_distance_km: float = Field(ge=0)
    travelled_route_km: float = Field(ge=0)
    remaining_route_km: float = Field(ge=0)

    tick_count: int = Field(ge=0)
    updated_at: datetime | None

    trip_status: str
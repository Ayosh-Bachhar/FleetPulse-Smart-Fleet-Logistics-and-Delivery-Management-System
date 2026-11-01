from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.route_distance_and_time_schemas import (
    RouteStopResponse,
)


class ApplyStopSequenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_token: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )


class SequenceVariantResponse(BaseModel):
    stops: list[RouteStopResponse]

    distance_km: float = Field(ge=0)
    duration_minutes: float = Field(ge=0)
    straight_line_km: float = Field(ge=0)

    source: Literal["geoapify", "demo_estimate"]


class StopSequenceResponse(BaseModel):
    trip_id: str
    algorithm: str = (
        "precedence-aware nearest neighbour"
    )

    is_applied: bool
    sequence_changed: bool
    can_apply: bool

    preview_token: str | None = None

    original: SequenceVariantResponse
    optimized: SequenceVariantResponse

    distance_saved_km: float
    time_saved_minutes: float
    distance_saved_percent: float

    applied_at: datetime | None = None
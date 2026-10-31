from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RouteStopResponse(BaseModel):
    order_id: str
    kind: Literal["pickup", "delivery"]
    address: str
    latitude: float
    longitude: float


class TripRouteResponse(BaseModel):
    id: str
    trip_id: str

    distance_km: float = Field(ge=0)
    duration_minutes: float = Field(ge=0)

    source: Literal["geoapify", "demo_estimate"]
    is_estimate: bool
    from_saved_route: bool

    stops: list[RouteStopResponse]
    geometry: dict[str, Any]

    calculated_at: datetime


class RouteStatusResponse(BaseModel):
    trip_id: str
    calculated: bool
    source: str | None = None
from datetime import datetime, timezone
from typing import Any, Literal

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.models.route import RouteStop


RouteSource = Literal["geoapify", "demo_estimate"]


class TripRoute(Document):
    trip_id: PydanticObjectId

    # F12: Current route.
    stops: list[RouteStop] = Field(min_length=2)
    geometry: dict[str, Any]

    distance_m: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    duration_s: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    source: RouteSource

    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # F13: Preserve original route before optimization.
    # Optional fields keep existing F12 documents valid.
    original_stops: list[RouteStop] | None = None
    original_geometry: dict[str, Any] | None = None

    original_distance_m: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    original_duration_s: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    original_source: RouteSource | None = None

    original_straight_line_m: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    optimized_straight_line_m: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    optimized_at: datetime | None = None

    class Settings:
        name = "trip_routes"

        indexes = [
            IndexModel(
                [("trip_id", ASCENDING)],
                unique=True,
                name="unique_trip_route",
            ),
        ]
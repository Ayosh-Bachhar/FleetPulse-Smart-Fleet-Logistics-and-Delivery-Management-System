from datetime import datetime, timezone
from typing import Any, Literal

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.models.route import RouteStop


RouteSource = Literal["geoapify", "demo_estimate"]


class TripRoute(Document):
    trip_id: PydanticObjectId

    # Coordinates on stops use latitude/longitude.
    stops: list[RouteStop] = Field(min_length=2)

    # GeoJSON MultiLineString:
    # coordinates are [longitude, latitude].
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

    class Settings:
        name = "trip_routes"

        indexes = [
            IndexModel(
                [("trip_id", ASCENDING)],
                unique=True,
                name="unique_trip_route",
            ),
        ]
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class Vehicle(Document):
    registration_number: str
    vehicle_type: str
    capacity_kg: float = Field(gt=0)
    status: str = "available"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "vehicles"
        indexes = ["registration_number"]
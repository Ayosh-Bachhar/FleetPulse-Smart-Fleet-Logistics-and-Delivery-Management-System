from datetime import datetime, timezone
from enum import Enum

from beanie import Document
from pydantic import Field, field_validator
from pymongo import ASCENDING, IndexModel


DEFAULT_SERVICE_INTERVAL_KM = 5000.0


class VehicleStatus(str, Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"


class Vehicle(Document):
    registration_number: str = Field(
        min_length=3,
        max_length=32,
    )

    vehicle_type: str = Field(
        min_length=2,
        max_length=60,
    )

    capacity_kg: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    volume_capacity_m3: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )

    fuel_type: str | None = Field(
        default=None,
        min_length=2,
        max_length=40,
    )

    status: VehicleStatus = VehicleStatus.AVAILABLE

    # F4: simulated maintenance mileage
    odometer_km: float = Field(
        default=0,
        ge=0,
        allow_inf_nan=False,
    )

    last_service_km: float = Field(
        default=0,
        ge=0,
        allow_inf_nan=False,
    )

    service_interval_km: float = Field(
        default=DEFAULT_SERVICE_INTERVAL_KM,
        gt=0,
        allow_inf_nan=False,
    )

    maintenance_due: bool = False

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime | None = None

    @field_validator("registration_number", mode="before")
    @classmethod
    def normalize_registration(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("vehicle_type", "fuel_type", mode="before")
    @classmethod
    def normalize_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    class Settings:
        name = "vehicles"

        indexes = [
            IndexModel(
                [("registration_number", ASCENDING)],
                unique=True,
                name="unique_vehicle_registration",
            ),
        ]


def is_vehicle_maintenance_due(vehicle) -> bool:
    if getattr(vehicle, "maintenance_due", False):
        return True

    odometer = getattr(vehicle, "odometer_km", 0)
    last_service = getattr(vehicle, "last_service_km", 0)
    interval = getattr(
        vehicle,
        "service_interval_km",
        DEFAULT_SERVICE_INTERVAL_KM,
    )

    return odometer - last_service >= interval


def is_vehicle_dispatchable(vehicle) -> bool:
    return (
        vehicle.status == VehicleStatus.AVAILABLE
        and not is_vehicle_maintenance_due(vehicle)
    )
from datetime import date, datetime, timezone
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import Field, field_validator
from pymongo import ASCENDING, IndexModel


class DriverLicenseClass(str, Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class DriverStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INACTIVE = "inactive"


class Driver(Document):
    full_name: str = Field(min_length=2, max_length=100)

    phone: str | None = Field(
        default=None,
        max_length=20,
    )

    license_number: str = Field(
        min_length=5,
        max_length=40,
    )

    license_class: DriverLicenseClass
    license_expiry: date

    status: DriverStatus = DriverStatus.AVAILABLE

    # Optional link to an existing Driver-role User.
    user_id: PydanticObjectId | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if isinstance(value, str):
            return " ".join(value.split())
        return value

    @field_validator("license_number", mode="before")
    @classmethod
    def normalize_license(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    class Settings:
        name = "drivers"

        indexes = [
            IndexModel(
                [("license_number", ASCENDING)],
                unique=True,
                name="unique_driver_license",
            ),
            IndexModel(
                [("user_id", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "user_id": {"$type": "objectId"}
                },
                name="unique_driver_user",
            ),
            "full_name",
        ]
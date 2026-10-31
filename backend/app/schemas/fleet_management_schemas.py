import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.vehicle import VehicleStatus


REGISTRATION_PATTERN = re.compile(r"^[A-Z0-9-]{3,32}$")


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    volume_capacity_m3: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    fuel_type: str = Field(
        min_length=2,
        max_length=40,
    )

    status: VehicleStatus = VehicleStatus.AVAILABLE

    @field_validator("registration_number", mode="before")
    @classmethod
    def validate_registration(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()

            if not REGISTRATION_PATTERN.fullmatch(value):
                raise ValueError(
                    "Registration must contain 3-32 "
                    "letters, numbers or hyphens."
                )

        return value

    @field_validator("vehicle_type", "fuel_type", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class VehicleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_number: str | None = Field(
        default=None,
        min_length=3,
        max_length=32,
    )

    vehicle_type: str | None = Field(
        default=None,
        min_length=2,
        max_length=60,
    )

    capacity_kg: float | None = Field(
        default=None,
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

    status: VehicleStatus | None = None

    @field_validator("registration_number", mode="before")
    @classmethod
    def validate_registration(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()

            if not REGISTRATION_PATTERN.fullmatch(value):
                raise ValueError("Invalid registration number.")

        return value

    @field_validator("vehicle_type", "fuel_type", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")

        required_fields = {
            "registration_number",
            "vehicle_type",
            "capacity_kg",
            "status",
        }

        for field_name in required_fields:
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(
                    f"{field_name} cannot be null."
                )

        return self


class VehicleResponse(BaseModel):
    id: str
    registration_number: str
    vehicle_type: str
    capacity_kg: float
    volume_capacity_m3: float | None
    fuel_type: str | None
    status: VehicleStatus
    is_available: bool
    created_at: datetime
    updated_at: datetime | None


class VehicleListResponse(BaseModel):
    items: list[VehicleResponse]
    total: int
    page: int
    page_size: int
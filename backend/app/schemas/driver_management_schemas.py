import re
from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.driver import (
    DriverLicenseClass,
    DriverStatus,
)


LICENSE_PATTERN = re.compile(r"^[A-Z0-9/-]{5,40}$")
PHONE_PATTERN = re.compile(r"^\+?[0-9 -]{7,20}$")


class DriverFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("full_name", check_fields=False, mode="before")
    @classmethod
    def clean_name(cls, value):
        if isinstance(value, str):
            return " ".join(value.split())
        return value

    @field_validator("license_number", check_fields=False, mode="before")
    @classmethod
    def validate_license(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()
            if not LICENSE_PATTERN.fullmatch(value):
                raise ValueError(
                    "License number must contain 5-40 "
                    "letters, digits, hyphens or slashes."
                )
        return value

    @field_validator("phone", check_fields=False, mode="before")
    @classmethod
    def validate_phone(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if not PHONE_PATTERN.fullmatch(value):
                raise ValueError("Invalid phone number.")
        return value

    @field_validator(
        "linked_user_email",
        check_fields=False,
        mode="before",
    )
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower() or None
        return value


class DriverCreate(DriverFields):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    license_number: str = Field(
        min_length=5,
        max_length=40,
    )

    license_class: DriverLicenseClass
    license_expiry: date

    status: DriverStatus = DriverStatus.AVAILABLE

    linked_user_email: EmailStr | None = None


class DriverUpdate(DriverFields):
    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    phone: str | None = Field(
        default=None,
        max_length=20,
    )

    license_number: str | None = Field(
        default=None,
        min_length=5,
        max_length=40,
    )

    license_class: DriverLicenseClass | None = None
    license_expiry: date | None = None
    status: DriverStatus | None = None
    linked_user_email: EmailStr | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required.")

        required_fields = {
            "full_name",
            "license_number",
            "license_class",
            "license_expiry",
            "status",
        }

        for name in required_fields:
            if (
                name in self.model_fields_set
                and getattr(self, name) is None
            ):
                raise ValueError(f"{name} cannot be null.")

        return self


class DriverResponse(BaseModel):
    id: str
    full_name: str
    phone: str | None

    license_number: str
    license_class: DriverLicenseClass
    license_expiry: date

    status: DriverStatus
    user_id: str | None
    linked_user_email: str | None

    allowed_vehicle_types: list[str]
    license_valid: bool
    is_available: bool

    created_at: datetime
    updated_at: datetime | None


class DriverListResponse(BaseModel):
    items: list[DriverResponse]
    total: int
    page: int
    page_size: int


class DriverCompatibilityResponse(BaseModel):
    driver_id: str
    vehicle_id: str
    license_compatible: bool
    eligible_for_dispatch: bool
    reason: str
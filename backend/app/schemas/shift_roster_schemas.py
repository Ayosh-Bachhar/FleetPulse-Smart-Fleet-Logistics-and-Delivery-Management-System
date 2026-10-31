from datetime import datetime, timedelta

from bson import ObjectId
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.shift import ShiftStatus


def validate_shift_period(start_at, end_at):
    if end_at <= start_at:
        raise ValueError("End time must be after start time.")

    # Project scheduling convention: one shift <= 24 hours.
    if end_at - start_at > timedelta(hours=24):
        raise ValueError(
            "A shift cannot be longer than 24 hours."
        )


class ShiftFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "driver_id",
        "vehicle_id",
        check_fields=False,
    )
    @classmethod
    def validate_object_id(cls, value):
        if not isinstance(value, str) or not ObjectId.is_valid(value):
            raise ValueError("A valid MongoDB ID is required.")
        return value


class ShiftCreate(ShiftFields):
    driver_id: str
    vehicle_id: str

    start_at: AwareDatetime
    end_at: AwareDatetime

    @model_validator(mode="after")
    def validate_period(self):
        validate_shift_period(self.start_at, self.end_at)
        return self


class ShiftUpdate(ShiftFields):
    driver_id: str | None = None
    vehicle_id: str | None = None

    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None

    status: ShiftStatus | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required.")

        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(
                    f"{field_name} cannot be null."
                )

        if self.start_at and self.end_at:
            validate_shift_period(self.start_at, self.end_at)

        return self


class HolidayCheckResponse(BaseModel):
    is_holiday: bool
    holiday_names: list[str]
    source: str
    notice: str


class ShiftResponse(BaseModel):
    id: str

    driver_id: str
    driver_name: str

    vehicle_id: str
    vehicle_registration: str
    vehicle_type: str

    start_at: datetime
    end_at: datetime

    status: ShiftStatus

    holiday_names: list[str]
    holiday_source: str
    holiday_notice: str

    created_at: datetime
    updated_at: datetime | None


class ShiftListResponse(BaseModel):
    items: list[ShiftResponse]
    total: int
    page: int
    page_size: int
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.vehicle import VehicleStatus
from app.models.maintenance_record import MaintenanceEvent


class MaintenanceRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddMileageRequest(MaintenanceRequestBase):
    distance_km: float = Field(
        gt=0,
        le=10000,
        allow_inf_nan=False,
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class CompleteServiceRequest(MaintenanceRequestBase):
    notes: str = Field(
        min_length=3,
        max_length=500,
    )

    @field_validator("notes", mode="before")
    @classmethod
    def clean_notes(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class ChangeServiceIntervalRequest(MaintenanceRequestBase):
    service_interval_km: float = Field(
        gt=0,
        le=100000,
        allow_inf_nan=False,
    )

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class MaintenanceVehicleResponse(BaseModel):
    id: str
    registration_number: str
    vehicle_type: str
    status: VehicleStatus

    odometer_km: float
    last_service_km: float
    service_interval_km: float

    kilometers_since_service: float
    kilometers_until_service: float
    service_progress_percent: float

    maintenance_due: bool
    needs_attention: bool
    is_available: bool

    updated_at: datetime | None


class MaintenanceListResponse(BaseModel):
    items: list[MaintenanceVehicleResponse]
    total: int
    page: int
    page_size: int


class MaintenanceRecordResponse(BaseModel):
    id: str
    vehicle_id: str
    actor_user_id: str
    event_type: MaintenanceEvent

    distance_km: float
    odometer_km: float
    service_interval_km: float
    maintenance_triggered: bool

    notes: str | None
    created_at: datetime


class MaintenanceHistoryResponse(BaseModel):
    items: list[MaintenanceRecordResponse]
    total: int
    page: int
    page_size: int
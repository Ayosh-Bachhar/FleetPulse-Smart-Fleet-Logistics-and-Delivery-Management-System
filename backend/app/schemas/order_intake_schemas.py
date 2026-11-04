from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.order import OrderStatus


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pickup_address: str = Field(
        min_length=5,
        max_length=500,
    )

    delivery_address: str = Field(
        min_length=5,
        max_length=500,
    )

    weight_kg: float = Field(
        gt=0,
        le=50000,
        allow_inf_nan=False,
    )

    length_cm: float = Field(
        ge=1,
        le=10000,
        allow_inf_nan=False,
    )

    width_cm: float = Field(
        ge=1,
        le=10000,
        allow_inf_nan=False,
    )

    height_cm: float = Field(
        ge=1,
        le=10000,
        allow_inf_nan=False,
    )

    is_rush: bool = False

    # Dispatcher only.
    # Customers cannot choose another account.
    customer_email: EmailStr | None = None

    @field_validator(
        "pickup_address",
        "delivery_address",
        mode="before",
    )
    @classmethod
    def normalize_address(cls, value):
        if isinstance(value, str):
            return " ".join(value.strip().split())
        return value

    @field_validator(
        "customer_email",
        mode="before",
    )
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower() or None
        return value

    @model_validator(mode="after")
    def validate_addresses(self):
        if (
            self.pickup_address.casefold()
            == self.delivery_address.casefold()
        ):
            raise ValueError(
                "Pickup and delivery addresses "
                "must be different."
            )

        return self


class OrderResponse(BaseModel):
    id: str
    reference_code: str

    customer_id: str
    customer_name: str
    customer_email: EmailStr

    pickup_address: str
    delivery_address: str

    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float
    volume_m3: float

    is_rush: bool
    status: OrderStatus

    trip_id: str | None
    public_tracking_uuid: str

    created_at: datetime
    updated_at: datetime | None


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
from datetime import datetime, timezone
from enum import Enum

from beanie import Document
from pydantic import EmailStr, Field, field_validator
from pymongo import ASCENDING, IndexModel


class Role(str, Enum):
    ADMIN = "admin"
    DISPATCHER = "dispatcher"
    DRIVER = "driver"
    CUSTOMER = "customer"


class User(Document):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    password_hash: str

    role: Role = Role.CUSTOMER
    is_active: bool = True

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Password reset information
    reset_token_hash: str | None = Field(
        default=None,
        repr=False,
    )

    reset_token_expires_at: datetime | None = None

    # Used to invalidate old sessions after password reset
    auth_version: int = Field(default=0, ge=0)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

    class Settings:
        name = "users"
        indexes = [
            IndexModel(
                [("email", ASCENDING)],
                unique=True,
                name="unique_user_email",
            )
        ]
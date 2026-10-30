from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.models.user import Role


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    password: str = Field(
        min_length=1,
        repr=False,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value


class LoginResponse(BaseModel):
    message: str = "Login successful"
    id: str
    full_name: str
    email: EmailStr
    role: Role
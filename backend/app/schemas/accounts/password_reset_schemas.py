from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value


class ForgotPasswordResponse(BaseModel):
    message: str = (
        "If the account exists, password reset "
        "instructions will be provided."
    )


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(
        min_length=32,
        max_length=256,
    )

    new_password: str = Field(
        min_length=8,
        repr=False,
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError(
                "Password must not exceed 72 bytes."
            )

        return value


class ResetPasswordResponse(BaseModel):
    message: str = "Password reset successfully."
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)


def normalize_email(value):
    return value.strip().lower() if isinstance(value, str) else value


def ascii_email(value: EmailStr) -> str:
    if not value.isascii():
        raise ValueError("International email addresses are not supported yet.")
    return str(value)


CanonicalEmail = Annotated[
    EmailStr, BeforeValidator(normalize_email), AfterValidator(ascii_email)
]


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: CanonicalEmail = Field(max_length=254)
    password: SecretStr

    @field_validator("password")
    @classmethod
    def bound_password(cls, value: SecretStr) -> SecretStr:
        if not 1 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Password length is invalid.")
        return value


class RegisterInput(LoginInput):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def passphrase_policy(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 15:
            raise ValueError("Use at least 15 characters.")
        return value


class VerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr

    @field_validator("token")
    @classmethod
    def bound_token(cls, value: SecretStr) -> SecretStr:
        if not 1 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Invalid token format.")
        return value


class UserSelf(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    email_verified_at: datetime | None
    is_active: bool
    created_at: datetime


class RegistrationOutput(BaseModel):
    user: UserSelf
    verification_delivery: Literal["not_configured"] = "not_configured"


class CSRFOutput(BaseModel):
    csrf_token: str

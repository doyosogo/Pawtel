from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.enums import PetSpecies


def trimmed(value):
    return value.strip() if isinstance(value, str) else value


def optional_breed(value):
    if isinstance(value, str):
        return value.strip() or None
    return value


def calendar_date(value):
    # JSON dates must be YYYY-MM-DD, not timestamps or datetime coercions.
    if value is None or type(value) is date:
        return value
    if (
        not isinstance(value, str)
        or len(value) != 10
        or value[4] != "-"
        or value[7] != "-"
    ):
        raise ValueError("Use a calendar date in YYYY-MM-DD format.")
    return value


def not_future(value: date | None) -> date | None:
    if value is not None and value > datetime.now(UTC).date():
        raise ValueError("Date of birth cannot be in the future.")
    return value


PetName = Annotated[str, Field(min_length=1, max_length=80), BeforeValidator(trimmed)]
PetBreed = Annotated[str | None, Field(max_length=100), BeforeValidator(optional_breed)]
BirthDate = Annotated[
    date | None, BeforeValidator(calendar_date), AfterValidator(not_future)
]


class PetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: PetName
    species: PetSpecies
    breed: PetBreed = None
    date_of_birth: BirthDate = None


class PetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: PetName | None = None
    species: PetSpecies | None = None
    breed: PetBreed = None
    date_of_birth: BirthDate = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one editable field.")
        if any(
            key in self.model_fields_set and getattr(self, key) is None
            for key in ("name", "species")
        ):
            raise ValueError("Name and species cannot be null.")
        return self


class PetOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    species: PetSpecies
    breed: str | None
    date_of_birth: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

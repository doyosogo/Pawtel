from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.enums import AustralianState, ListingStatus, PetSpecies

if TYPE_CHECKING:
    from app.models import Listing


def trimmed(value):
    return value.strip() if isinstance(value, str) else value


def optional_text(value):
    return value.strip() or None if isinstance(value, str) else value


def unique_species(value: list[PetSpecies]) -> list[PetSpecies]:
    if len(value) != len(set(value)):
        raise ValueError("Accepted species must not contain duplicates.")
    return value


Bio = Annotated[str | None, Field(max_length=2000), BeforeValidator(optional_text)]
Title = Annotated[str, Field(min_length=1, max_length=160), BeforeValidator(trimmed)]
Description = Annotated[
    str, Field(min_length=1, max_length=10000), BeforeValidator(trimmed)
]
Suburb = Annotated[str, Field(min_length=1, max_length=100), BeforeValidator(trimmed)]
Postcode = Annotated[
    str, Field(strict=True, pattern=r"^[0-9]{4}$"), BeforeValidator(trimmed)
]
# Keep JSON monetary integers exact for eventual JavaScript consumers, within BIGINT.
Cents = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]
Capacity = Annotated[int, Field(strict=True, ge=1, le=2147483647)]
AcceptedSpecies = Annotated[
    list[PetSpecies], Field(max_length=2), AfterValidator(unique_species)
]
EditableStatus = Literal[ListingStatus.DRAFT, ListingStatus.PUBLISHED]


class HostEnable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bio: Bio = None


class HostPatch(HostEnable):
    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set:
            raise ValueError("Provide an editable field.")
        return self


class HostOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    bio: str | None
    created_at: datetime
    updated_at: datetime


class ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    description: Description
    suburb: Suburb
    state: AustralianState
    postcode: Postcode
    country_code: Literal["AU"] = "AU"
    max_pet_capacity: Capacity
    base_nightly_price_cents: Cents
    additional_pet_price_cents: Cents
    accepted_species: AcceptedSpecies = Field(default_factory=list)


class ListingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title | None = None
    description: Description | None = None
    suburb: Suburb | None = None
    state: AustralianState | None = None
    postcode: Postcode | None = None
    country_code: Literal["AU"] | None = None
    max_pet_capacity: Capacity | None = None
    base_nightly_price_cents: Cents | None = None
    additional_pet_price_cents: Cents | None = None
    accepted_species: AcceptedSpecies | None = None
    status: EditableStatus | None = None

    @model_validator(mode="after")
    def valid_patch(self):
        if not self.model_fields_set:
            raise ValueError("Provide an editable field.")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Listing fields cannot be null.")
        return self


class ListingOutput(BaseModel):
    id: UUID
    title: str
    description: str
    suburb: str
    state: AustralianState
    postcode: str
    country_code: str
    max_pet_capacity: int
    base_nightly_price_cents: int
    additional_pet_price_cents: int
    status: ListingStatus
    accepted_species: list[PetSpecies]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_listing(cls, listing: Listing):
        return cls(
            id=listing.id,
            title=listing.title,
            description=listing.description,
            suburb=listing.suburb,
            state=listing.state,
            postcode=listing.postcode,
            country_code=listing.country_code,
            max_pet_capacity=listing.max_pet_capacity,
            base_nightly_price_cents=listing.base_nightly_price_cents,
            additional_pet_price_cents=listing.additional_pet_price_cents,
            status=listing.status,
            accepted_species=sorted(
                (row.species for row in listing.accepted_species),
                key=lambda species: species.value,
            ),
            created_at=listing.created_at,
            updated_at=listing.updated_at,
        )

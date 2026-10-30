from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AustralianState, PetSpecies
from app.schemas.host import Postcode, Suburb

Price = Annotated[int, Field(ge=0, le=9007199254740991)]
PetCount = Annotated[int, Field(ge=1, le=2147483647)]


class StayQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_in: date
    check_out: date
    pet_count: PetCount

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("Checkout must follow check-in.")
        return self


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: AustralianState | None = None
    suburb: Suburb | None = None
    postcode: Postcode | None = None
    species: list[PetSpecies] = Field(default_factory=list, max_length=2)
    min_price_cents: Price | None = None
    max_price_cents: Price | None = None
    pet_count: PetCount | None = None
    check_in: date | None = None
    check_out: date | None = None
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=2147483647)

    @model_validator(mode="after")
    def combinations(self):
        if len(self.species) != len(set(self.species)):
            raise ValueError("Duplicate species.")
        if self.check_in is not None or self.check_out is not None:
            StayQuery(
                check_in=self.check_in,
                check_out=self.check_out,
                pet_count=self.pet_count,
            )
        if (
            self.min_price_cents is not None
            and self.max_price_cents is not None
            and self.min_price_cents > self.max_price_cents
        ):
            raise ValueError("Minimum price exceeds maximum.")
        return self


class PublicHost(BaseModel):
    display_name: str
    bio: str | None


class PublicListing(BaseModel):
    id: UUID
    title: str
    description: str
    suburb: str
    state: AustralianState
    postcode: str
    country_code: str
    base_nightly_price_cents: int
    additional_pet_price_cents: int
    max_pet_capacity: int
    accepted_species: list[PetSpecies]
    host: PublicHost


class ListingPage(BaseModel):
    items: list[PublicListing]
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class Availability(StayQuery):
    listing_id: UUID
    available: bool
    remaining_capacity_at_tightest_point: int

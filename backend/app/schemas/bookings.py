from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import BookingStatus, PetSpecies


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    listing_id: UUID
    pet_ids: list[UUID] = Field(min_length=1, max_length=100)
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def unique_pets(self):
        if len(self.pet_ids) != len(set(self.pet_ids)):
            raise ValueError("Duplicate pets.")
        return self


class EmptyAction(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BookingListing(BaseModel):
    id: UUID
    title: str
    suburb: str
    state: str


class BookingPetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    species: PetSpecies
    breed: str | None
    date_of_birth: date | None
    is_active: bool


class BookingOutput(BaseModel):
    id: UUID
    listing: BookingListing
    pets: list[BookingPetSummary]
    owner_display_name: str
    check_in: date
    check_out: date
    status: BookingStatus
    nightly_base_price_cents: int
    additional_pet_price_cents: int
    subtotal_cents: int
    service_fee_cents: int
    total_cents: int
    payment_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

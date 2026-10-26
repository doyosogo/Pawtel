from enum import StrEnum

from sqlalchemy import Enum

from app.db.base import Base


class PetSpecies(StrEnum):
    DOG = "DOG"
    CAT = "CAT"


class AustralianState(StrEnum):
    ACT = "ACT"
    NSW = "NSW"
    NT = "NT"
    QLD = "QLD"
    SA = "SA"
    TAS = "TAS"
    VIC = "VIC"
    WA = "WA"


class ListingStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class BookingStatus(StrEnum):
    REQUESTED = "REQUESTED"
    DECLINED = "DECLINED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


# One shared PostgreSQL type per enum, including the species used by two tables.
pet_species_type = Enum(PetSpecies, name="pet_species", metadata=Base.metadata)
australian_state_type = Enum(
    AustralianState, name="australian_state", metadata=Base.metadata
)
listing_status_type = Enum(ListingStatus, name="listing_status", metadata=Base.metadata)
booking_status_type = Enum(BookingStatus, name="booking_status", metadata=Base.metadata)

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import Timestamps, UUIDPrimaryKey
from app.models.enums import (
    AustralianState,
    ListingStatus,
    PetSpecies,
    australian_state_type,
    listing_status_type,
    pet_species_type,
)

if TYPE_CHECKING:
    from app.models.accounts import HostProfile
    from app.models.bookings import Booking


class Listing(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("btrim(suburb) <> ''", name="suburb_not_blank"),
        CheckConstraint("postcode ~ '^[0-9]{4}$'", name="postcode_format"),
        CheckConstraint("country_code = 'AU'", name="country_australia"),
        CheckConstraint("max_pet_capacity > 0", name="capacity_positive"),
        CheckConstraint("base_nightly_price_cents >= 0", name="base_price_nonnegative"),
        CheckConstraint(
            "additional_pet_price_cents >= 0", name="extra_price_nonnegative"
        ),
    )

    host_id: Mapped[UUID] = mapped_column(
        ForeignKey("host_profiles.user_id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    suburb: Mapped[str] = mapped_column(String(100))
    state: Mapped[AustralianState] = mapped_column(australian_state_type)
    postcode: Mapped[str] = mapped_column(String(4))
    country_code: Mapped[str] = mapped_column(String(2), server_default="AU")
    max_pet_capacity: Mapped[int]
    base_nightly_price_cents: Mapped[int] = mapped_column(BigInteger)
    additional_pet_price_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[ListingStatus] = mapped_column(
        listing_status_type, server_default=ListingStatus.DRAFT.value
    )

    host: Mapped[HostProfile] = relationship(back_populates="listings")
    accepted_species: Mapped[list[ListingAcceptedSpecies]] = relationship(
        back_populates="listing", cascade="all, delete-orphan", passive_deletes=True
    )
    bookings: Mapped[list[Booking]] = relationship(
        back_populates="listing", passive_deletes="all"
    )


class ListingAcceptedSpecies(Base):
    __tablename__ = "listing_accepted_species"

    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    species: Mapped[PetSpecies] = mapped_column(pet_species_type, primary_key=True)

    listing: Mapped[Listing] = relationship(back_populates="accepted_species")

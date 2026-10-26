from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import Timestamps, UUIDPrimaryKey
from app.models.enums import BookingStatus, booking_status_type

if TYPE_CHECKING:
    from app.models.accounts import User
    from app.models.listings import Listing
    from app.models.pets import Pet


class Booking(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_date > start_date", name="dates_ordered"),
        CheckConstraint("nightly_base_price_cents >= 0", name="base_price_nonnegative"),
        CheckConstraint(
            "additional_pet_price_cents >= 0", name="extra_price_nonnegative"
        ),
        CheckConstraint("subtotal_cents >= 0", name="subtotal_nonnegative"),
        CheckConstraint("service_fee_cents >= 0", name="fee_nonnegative"),
        CheckConstraint("total_cents >= 0", name="total_nonnegative"),
        CheckConstraint(
            "total_cents = subtotal_cents + service_fee_cents",
            name="total_matches_parts",
        ),
        CheckConstraint(
            "status <> 'AWAITING_PAYMENT' OR payment_expires_at IS NOT NULL",
            name="payment_hold_has_deadline",
        ),
        Index(
            "ix_bookings_listing_status_dates",
            "listing_id",
            "status",
            "start_date",
            "end_date",
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="RESTRICT")
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[BookingStatus] = mapped_column(
        booking_status_type, server_default=BookingStatus.REQUESTED.value
    )
    payment_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nightly_base_price_cents: Mapped[int] = mapped_column(BigInteger)
    additional_pet_price_cents: Mapped[int] = mapped_column(BigInteger)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger)
    service_fee_cents: Mapped[int] = mapped_column(BigInteger)
    total_cents: Mapped[int] = mapped_column(BigInteger)

    owner: Mapped[User] = relationship(back_populates="bookings")
    listing: Mapped[Listing] = relationship(back_populates="bookings")
    booking_pets: Mapped[list[BookingPet]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", passive_deletes=True
    )


class BookingPet(Base):
    __tablename__ = "booking_pets"
    __table_args__ = (Index("ix_booking_pets_pet_id", "pet_id"),)

    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets.id", ondelete="RESTRICT"), primary_key=True
    )

    booking: Mapped[Booking] = relationship(back_populates="booking_pets")
    pet: Mapped[Pet] = relationship(back_populates="booking_pets")

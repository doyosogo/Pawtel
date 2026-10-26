from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import Timestamps, UUIDPrimaryKey
from app.models.enums import PetSpecies, pet_species_type

if TYPE_CHECKING:
    from app.models.accounts import User
    from app.models.bookings import BookingPet


class Pet(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "pets"
    __table_args__ = (CheckConstraint("btrim(name) <> ''", name="name_not_blank"),)

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    species: Mapped[PetSpecies] = mapped_column(pet_species_type)
    breed: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    owner: Mapped[User] = relationship(back_populates="pets")
    booking_pets: Mapped[list[BookingPet]] = relationship(
        back_populates="pet", passive_deletes="all"
    )

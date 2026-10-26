from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.models.common import Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.bookings import Booking
    from app.models.listings import Listing
    from app.models.pets import Pet


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email = lower(btrim(email)) AND email <> '' AND email !~ '[[:space:]]'",
            name="email_normalized",
        ),
        CheckConstraint("btrim(display_name) <> ''", name="display_name_not_blank"),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    host_profile: Mapped[HostProfile | None] = relationship(
        back_populates="user", passive_deletes="all"
    )
    pets: Mapped[list[Pet]] = relationship(
        back_populates="owner", passive_deletes="all"
    )
    bookings: Mapped[list[Booking]] = relationship(
        back_populates="owner", passive_deletes="all"
    )

    @validates("email")
    def normalize_email(self, key: str, value: str) -> str:
        return value.strip().lower()


class HostProfile(Timestamps, Base):
    __tablename__ = "host_profiles"

    # Shared UUID primary key makes Host mode genuinely one-to-one with an account.
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    bio: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="host_profile")
    listings: Mapped[list[Listing]] = relationship(
        back_populates="host", passive_deletes="all"
    )

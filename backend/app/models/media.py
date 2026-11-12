from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.listings import Listing


class ListingImage(UUIDPrimaryKey, Base):
    __tablename__ = "listing_images"
    __table_args__ = (
        CheckConstraint(
            "status IN ('UPLOADING','READY','DELETE_PENDING')", name="status_valid"
        ),
        CheckConstraint("sort_order >= 0", name="sort_nonnegative"),
    )
    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="RESTRICT"), index=True
    )
    public_id: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str] = mapped_column(String(600))
    alt_text: Mapped[str] = mapped_column(String(160), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), default="UPLOADING", server_default="UPLOADING"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    listing: Mapped[Listing] = relationship(back_populates="images")

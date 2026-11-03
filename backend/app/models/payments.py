"""Persist payment identity/state, never credentials, bodies or client secrets."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import Timestamps, UUIDPrimaryKey

ACTIVE_ATTEMPTS = ("CREATING", "OPEN", "REQUIRES_RECONCILIATION")


class PaymentAttempt(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        CheckConstraint("provider = 'stripe'", name="provider_stripe"),
        CheckConstraint("currency = 'aud'", name="currency_aud"),
        CheckConstraint(
            "amount_cents >= 0 AND subtotal_cents >= 0 AND service_fee_cents >= 0",
            name="amounts_nonnegative",
        ),
        CheckConstraint(
            "amount_cents = subtotal_cents + service_fee_cents",
            name="amount_matches_parts",
        ),
        CheckConstraint(
            "status IN ('CREATING','OPEN','SUCCEEDED','EXPIRED','FAILED',"
            "'CANCELLED','REQUIRES_RECONCILIATION')",
            name="status_valid",
        ),
        CheckConstraint("expires_at > created_at", name="expiry_ordered"),
        Index(
            "uq_payment_attempt_active_booking",
            "booking_id",
            unique=True,
            postgresql_where=text(
                "status IN ('CREATING','OPEN','REQUIRES_RECONCILIATION')"
            ),
        ),
    )
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(10), server_default="stripe")
    status: Mapped[str] = mapped_column(String(30), server_default="CREATING")
    checkout_session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger)
    service_fee_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), server_default="aud")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    return_url: Mapped[str] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciliation_reason: Mapped[str | None] = mapped_column(String(80))


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"
    __table_args__ = (
        CheckConstraint(
            "result IN ('RECEIVED','PROCESSED','IGNORED','REJECTED','RECONCILIATION')",
            name="result_valid",
        ),
    )
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100))
    object_id: Mapped[str | None] = mapped_column(String(255), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str] = mapped_column(String(20), server_default="RECEIVED")

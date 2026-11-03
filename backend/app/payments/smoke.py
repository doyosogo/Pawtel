"""Explicit online sandbox smoke: creates/expires an unpaid synthetic Session only."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import get_settings
from app.models import Booking, PaymentAttempt
from app.payments.gateway import StripeGateway
from app.services.pricing import quote


def main():
    settings = get_settings()
    gateway = StripeGateway(settings)  # Rejects missing/live keys before any request.
    booking = Booking(id=uuid4(), **asdict(quote(5000, 1000, 1, 2)))
    attempt = PaymentAttempt(
        id=uuid4(),
        booking_id=booking.id,
        amount_cents=booking.total_cents,
        subtotal_cents=booking.subtotal_cents,
        service_fee_cents=booking.service_fee_cents,
        expires_at=(datetime.now(UTC) + timedelta(seconds=3660)).replace(microsecond=0),
        return_url=settings.stripe_return_url,
    )
    session = None
    try:
        first = gateway.create(attempt)
        session = first.id
        second = gateway.create(attempt)
        assert first.id == second.id
        assert first.amount == second.amount == booking.total_cents == 11000
        assert first.currency == second.currency == "aud"
        assert first.metadata == {
            "booking_id": str(booking.id),
            "payment_attempt_id": str(attempt.id),
        }
        assert first.expires_at == int(attempt.expires_at.timestamp())
        remaining = first.expires_at - datetime.now(UTC).timestamp()
        assert 1800 < remaining <= 86400
        # Gateway validates livemode=false, mode=payment and the cs_test_ identifier.
        print(
            "Sandbox creation/retry PASS: test-only, AUD 11000 cents; "
            "matching IDs/metadata,"
        )
        print("valid provider expiry, same Session on deterministic idempotent retry.")
    finally:
        if session:
            gateway.expire(session)
            print("Synthetic unpaid Checkout Session expired; no card charged.")


if __name__ == "__main__":
    main()

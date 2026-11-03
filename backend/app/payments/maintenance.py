"""Explicit recovery/expiry command; no scheduler and no payment confirmation bypass."""

import argparse
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.models import Booking, PaymentAttempt
from app.models.enums import BookingStatus
from app.models.payments import ACTIVE_ATTEMPTS
from app.payments.gateway import ProviderRejected, ProviderUncertain, StripeGateway
from app.payments.service import cleanup_cancelled, expire_unstarted, record_session


def reconcile(db, booking_id, gateway):
    with db.begin():
        booking = db.get(Booking, booking_id)
        if booking is None:
            return "SKIPPED"
        cancelled = booking.status == BookingStatus.CANCELLED
        overdue = (
            booking.status == BookingStatus.AWAITING_PAYMENT
            and booking.payment_expires_at <= datetime.now(UTC)
        )
        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.booking_id == booking_id,
                PaymentAttempt.status.in_(ACTIVE_ATTEMPTS),
            )
        )
    if cancelled:
        cleanup_cancelled(db, booking_id, gateway)
        return "CLEANUP_ATTEMPTED"
    if not overdue:
        return "SKIPPED"
    if attempt is None:
        return "EXPIRED" if expire_unstarted(db, booking_id) else "SKIPPED"
    try:
        session = (
            gateway.retrieve(attempt.checkout_session_id)
            if attempt.checkout_session_id
            else gateway.create(attempt)
        )
        if session.status == "open":
            session = gateway.expire(session.id)
        return record_session(db, attempt.id, session)
    except ProviderRejected, ProviderUncertain:
        # Unknown provider outcome must never be treated as proof of no payment.
        return "UNRESOLVED"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--booking-id", type=UUID)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit must be between 1 and 1000")
    settings = get_settings()
    with Session(get_engine(), expire_on_commit=False) as db:
        with db.begin():
            query = select(Booking.id).where(
                Booking.status.in_(
                    [BookingStatus.CANCELLED, BookingStatus.AWAITING_PAYMENT]
                )
            )
            if args.booking_id:
                query = query.where(Booking.id == args.booking_id)
            else:
                query = query.where(
                    (Booking.payment_expires_at <= datetime.now(UTC))
                    | (
                        (Booking.status == BookingStatus.CANCELLED)
                        & select(PaymentAttempt.id)
                        .where(
                            PaymentAttempt.booking_id == Booking.id,
                            PaymentAttempt.status.in_(ACTIVE_ATTEMPTS),
                        )
                        .exists()
                    )
                )
            ids = list(db.scalars(query.order_by(Booking.id).limit(args.limit)))
        gateway = StripeGateway(settings) if settings.stripe_secret_key else None
        counts = {}
        for booking_id in ids:
            if gateway is None:
                result = "EXPIRED" if expire_unstarted(db, booking_id) else "UNRESOLVED"
            else:
                result = reconcile(db, booking_id, gateway)
            counts[result] = counts.get(result, 0) + 1
        print("Payment maintenance results:", counts)


if __name__ == "__main__":
    main()

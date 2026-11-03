"""Short Listing-first transactions around, never across, provider calls."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.models import Booking, Listing, PaymentAttempt
from app.models.enums import BookingStatus
from app.models.payments import ACTIVE_ATTEMPTS
from app.payments.gateway import Checkout, ProviderRejected, ProviderUncertain


def locked_booking(db, booking_id, owner_id=None):
    db.execute(text("SET LOCAL lock_timeout = '5s'"))
    query = select(Booking.listing_id).where(Booking.id == booking_id)
    if owner_id is not None:
        query = query.where(Booking.owner_id == owner_id)
    listing_id = db.scalar(query)
    if listing_id is None:
        raise APIError(404, "booking_not_found", "Booking not found.")
    db.scalar(
        select(Listing)
        .where(Listing.id == listing_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def mark_reconciliation(attempt, reason):
    if attempt.status != "SUCCEEDED":
        attempt.status = "REQUIRES_RECONCILIATION"
        attempt.reconciliation_reason = reason


def identity_matches(attempt, booking, session: Checkout):
    return (
        session.metadata
        == {"booking_id": str(booking.id), "payment_attempt_id": str(attempt.id)}
        and session.currency == attempt.currency == "aud"
        and session.amount == attempt.amount_cents == booking.total_cents
        and session.expires_at == int(attempt.expires_at.timestamp())
        and (
            attempt.checkout_session_id is None
            or attempt.checkout_session_id == session.id
        )
        and (
            attempt.payment_intent_id is None
            or attempt.payment_intent_id == session.payment_intent
        )
    )


def apply_session(booking, attempt, session, source):
    """Caller holds Listing, Booking, attempt. Success ONLY from signed webhook."""
    if not identity_matches(attempt, booking, session):
        mark_reconciliation(attempt, "PROVIDER_IDENTITY_OR_AMOUNT_MISMATCH")
        return "REJECTED"
    attempt.checkout_session_id = session.id
    if session.payment_intent:
        attempt.payment_intent_id = session.payment_intent
    paid = session.payment_status == "paid" or (
        session.payment_status == "no_payment_required" and session.amount == 0
    )
    if session.status == "complete" and paid:
        if attempt.completed_at is None:
            attempt.completed_at = datetime.now(UTC)
        if attempt.status == "SUCCEEDED" and booking.status == BookingStatus.CONFIRMED:
            return "PROCESSED"
        if source != "webhook":
            mark_reconciliation(attempt, "PAID_AWAITING_VERIFIED_WEBHOOK")
            return "RECONCILIATION"
        if booking.status == BookingStatus.AWAITING_PAYMENT:
            booking.status = BookingStatus.CONFIRMED
            attempt.status = "SUCCEEDED"
            attempt.reconciliation_reason = None
            return "PROCESSED"
        mark_reconciliation(attempt, "PAID_BOOKING_NOT_PAYABLE")
        return "RECONCILIATION"
    # Never erase observed paid/mismatched-money reconciliation with an older expiry.
    if attempt.status == "REQUIRES_RECONCILIATION" and (
        attempt.completed_at is not None
        or attempt.reconciliation_reason
        in {"PROVIDER_IDENTITY_OR_AMOUNT_MISMATCH", "PROVIDER_RESPONSE_MISMATCH"}
    ):
        return "RECONCILIATION"
    # Out-of-order expiry must never regress a successful payment/confirmed stay.
    if attempt.status == "SUCCEEDED" or booking.status == BookingStatus.CONFIRMED:
        return "IGNORED"
    if session.status == "expired" and session.payment_status == "unpaid":
        attempt.status = (
            "CANCELLED" if booking.status == BookingStatus.CANCELLED else "EXPIRED"
        )
        attempt.reconciliation_reason = None
        if booking.status == BookingStatus.AWAITING_PAYMENT:
            booking.status = BookingStatus.EXPIRED
        return "PROCESSED"
    return "IGNORED"


def prepare(db: Session, owner_id: UUID, booking_id: UUID, return_url: str):
    with db.begin():
        booking = locked_booking(db, booking_id, owner_id)
        now = datetime.now(UTC)
        if booking.status != BookingStatus.AWAITING_PAYMENT:
            raise APIError(
                409, "booking_not_payable", "Booking is not awaiting payment."
            )
        if booking.payment_expires_at is None or booking.payment_expires_at <= now:
            raise APIError(409, "payment_window_closed", "Payment window has closed.")
        attempts = list(
            db.scalars(
                select(PaymentAttempt)
                .where(PaymentAttempt.booking_id == booking.id)
                .order_by(PaymentAttempt.created_at, PaymentAttempt.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        active = next((a for a in attempts if a.status in ACTIVE_ATTEMPTS), None)
        if active:
            if active.status == "REQUIRES_RECONCILIATION":
                raise APIError(
                    409,
                    "payment_reconciliation_required",
                    "Payment requires reconciliation.",
                )
            return active
        # First Checkout grants one bounded hour. New attempts reuse that same deadline.
        expiry = attempts[0].expires_at if attempts else now + timedelta(seconds=3660)
        if expiry < now + timedelta(seconds=1860):
            raise APIError(
                409, "payment_window_closed", "Insufficient remaining checkout window."
            )
        booking.payment_expires_at = expiry
        attempt = PaymentAttempt(
            booking_id=booking.id,
            amount_cents=booking.total_cents,
            subtotal_cents=booking.subtotal_cents,
            service_fee_cents=booking.service_fee_cents,
            expires_at=expiry.replace(microsecond=0),
            return_url=return_url,
        )
        # Exact provider second boundary is also PAWTEL's hold boundary.
        booking.payment_expires_at = attempt.expires_at
        db.add(attempt)
        db.flush()
        return attempt


def record_session(db, attempt_id, session):
    with db.begin():
        bid = db.scalar(
            select(PaymentAttempt.booking_id).where(PaymentAttempt.id == attempt_id)
        )
        booking = locked_booking(db, bid)
        attempt = db.scalar(
            select(PaymentAttempt)
            .where(PaymentAttempt.id == attempt_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not identity_matches(attempt, booking, session):
            mark_reconciliation(attempt, "PROVIDER_RESPONSE_MISMATCH")
        elif booking.status != BookingStatus.AWAITING_PAYMENT:
            apply_session(booking, attempt, session, "response")
            if attempt.status not in {"SUCCEEDED", "EXPIRED", "CANCELLED"}:
                mark_reconciliation(attempt, "CANCEL_CLEANUP_PENDING")
        elif attempt.status == "CREATING" and session.status == "open":
            attempt.checkout_session_id = session.id
            attempt.status = "OPEN"
        else:
            apply_session(booking, attempt, session, "response")
        db.flush()
        return attempt.status


def start(db, owner_id, booking_id, settings, gateway):
    attempt = prepare(db, owner_id, booking_id, settings.stripe_return_url)
    try:
        session = (
            gateway.retrieve(attempt.checkout_session_id)
            if attempt.checkout_session_id
            else gateway.create(attempt)
        )
    except ProviderRejected:
        # Only a definite create rejection means no Session was established.
        with db.begin():
            locked_booking(db, booking_id, owner_id)
            current = db.scalar(
                select(PaymentAttempt)
                .where(PaymentAttempt.id == attempt.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if current.status == "CREATING":
                current.status = "FAILED"
            else:
                mark_reconciliation(current, "PROVIDER_LOOKUP_REJECTED")
        raise APIError(
            502, "checkout_rejected", "Checkout could not be created."
        ) from None
    except ProviderUncertain:
        raise APIError(
            503,
            "checkout_temporarily_unavailable",
            "Checkout outcome is uncertain; retry this booking.",
        ) from None
    status = record_session(db, attempt.id, session)
    if status != "OPEN" or not session.client_secret or session.status != "open":
        if status == "REQUIRES_RECONCILIATION":
            cleanup_cancelled(db, booking_id, gateway)
        raise APIError(
            409, "checkout_not_open", "Checkout is not open; reload booking status."
        )
    return {
        "payment_attempt_id": attempt.id,
        "client_secret": session.client_secret,
        "expires_at": attempt.expires_at,
    }


def cleanup_cancelled(db, booking_id, gateway):
    # Pending state was committed by cancellation. No lock survives this snapshot.
    with db.begin():
        booking = db.get(Booking, booking_id)
        if booking is None or booking.status != BookingStatus.CANCELLED:
            return
        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.booking_id == booking_id,
                PaymentAttempt.status.in_(ACTIVE_ATTEMPTS),
            )
        )
    if attempt is None:
        return
    try:
        session = (
            gateway.retrieve(attempt.checkout_session_id)
            if attempt.checkout_session_id
            else gateway.create(attempt)
        )
        if session.status == "open":
            session = gateway.expire(session.id)
        record_session(db, attempt.id, session)
    except ProviderUncertain, ProviderRejected:
        # Retain CANCEL_CLEANUP_PENDING; later retry can recover the same identity.
        return


def expire_unstarted(db, booking_id):
    """Explicit expiry; unresolved provider attempts conservatively block release."""
    with db.begin():
        booking = locked_booking(db, booking_id)
        exists = db.scalar(
            select(PaymentAttempt.id).where(
                PaymentAttempt.booking_id == booking_id,
                PaymentAttempt.status.in_(ACTIVE_ATTEMPTS),
            )
        )
        if (
            not exists
            and booking.status == BookingStatus.AWAITING_PAYMENT
            and booking.payment_expires_at <= datetime.now(UTC)
        ):
            booking.status = BookingStatus.EXPIRED
            return True
        return False

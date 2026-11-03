"""Signed snapshot events; receipts and booking/payment mutations commit together."""

from datetime import UTC, datetime
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.api.errors import APIError
from app.models import PaymentAttempt, StripeWebhookEvent
from app.payments.gateway import ProviderUncertain, parse_session
from app.payments.service import apply_session, locked_booking

SUPPORTED = {"checkout.session.completed", "checkout.session.expired"}


def verified_event(body, signature, settings):
    if not settings.stripe_webhook_secret:
        raise APIError(503, "webhook_not_configured", "Webhook is not configured.")
    try:
        event = stripe.Webhook.construct_event(
            body,
            signature or "",
            settings.stripe_webhook_secret.get_secret_value(),
            tolerance=300,
        ).to_dict()
        if event.get("livemode") is not False:
            raise ValueError("Not test mode")
        if (
            not isinstance(event.get("id"), str)
            or not event["id"].startswith("evt_")
            or len(event["id"]) > 255
        ):
            raise ValueError("Invalid event")
        if not isinstance(event.get("type"), str) or len(event["type"]) > 100:
            raise ValueError("Invalid event")
        return event
    except (
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        stripe.SignatureVerificationError,
    ):
        raise APIError(400, "invalid_webhook", "Invalid Stripe webhook.") from None


def process(db, event):
    data = event.get("data")
    obj = data.get("object", {}) if isinstance(data, dict) else {}
    if not isinstance(obj, dict):
        obj = {}
    object_id = obj.get("id")
    if not isinstance(object_id, str) or len(object_id) > 255:
        object_id = None
    with db.begin():
        receipt_id = db.scalar(
            insert(StripeWebhookEvent)
            .values(id=event["id"], event_type=event["type"], object_id=object_id)
            .on_conflict_do_nothing(index_elements=[StripeWebhookEvent.id])
            .returning(StripeWebhookEvent.id)
        )
        if receipt_id is None:
            return  # A concurrent insert waits for the first transaction's outcome.
        receipt = db.get(StripeWebhookEvent, receipt_id)
        receipt.result = "IGNORED"
        if event["type"] in SUPPORTED:
            try:
                session = parse_session(obj)
                attempt_id = UUID(session.metadata.get("payment_attempt_id", ""))
            except ProviderUncertain, ValueError, TypeError, AttributeError:
                receipt.result = "REJECTED"
            else:
                bid = db.scalar(
                    select(PaymentAttempt.booking_id).where(
                        PaymentAttempt.id == attempt_id
                    )
                )
                if bid is None:
                    receipt.result = "REJECTED"
                else:
                    booking = locked_booking(db, bid)
                    attempt = db.scalar(
                        select(PaymentAttempt)
                        .where(PaymentAttempt.id == attempt_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                    # Event type must agree with the contained Session's terminal state.
                    expected = (
                        "complete" if event["type"].endswith("completed") else "expired"
                    )
                    if session.status != expected:
                        receipt.result = "REJECTED"
                    else:
                        receipt.result = apply_session(
                            booking, attempt, session, "webhook"
                        )
        receipt.processed_at = datetime.now(UTC)

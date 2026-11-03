"""Official SDK boundary. Never log provider payloads, exceptions or client secrets."""

import logging
from dataclasses import dataclass, field

import stripe

from app.api.errors import APIError
from app.core.config import Settings

# SDK debug/request logging can include payloads. Application owns safe error codes.
logging.getLogger("stripe").disabled = True


class ProviderUncertain(Exception):
    pass


class ProviderRejected(Exception):
    pass


@dataclass(frozen=True)
class Checkout:
    id: str
    amount: int
    currency: str
    status: str
    payment_status: str
    expires_at: int
    metadata: dict
    payment_intent: str | None = None
    client_secret: str | None = field(default=None, repr=False)


def parse_session(obj) -> Checkout:
    try:
        if hasattr(obj, "to_dict"):
            obj = obj.to_dict()
        if obj.get("mode") != "payment":
            raise ValueError("Not payment mode")
        if obj["livemode"] is not False or not obj["id"].startswith("cs_test_"):
            raise ValueError("Not test mode")
        if type(obj["amount_total"]) is not int or type(obj["expires_at"]) is not int:
            raise ValueError("Invalid numeric fields")
        if obj["status"] not in {"open", "complete", "expired"}:
            raise ValueError("Invalid status")
        intent = obj.get("payment_intent")
        if intent is not None and (
            not isinstance(intent, str) or not intent.startswith("pi_")
        ):
            raise ValueError("Invalid payment intent")
        return Checkout(
            obj["id"],
            obj["amount_total"],
            obj["currency"],
            obj["status"],
            obj["payment_status"],
            obj["expires_at"],
            dict(obj["metadata"]),
            intent,
            obj.get("client_secret"),
        )
    except KeyError, TypeError, ValueError, AttributeError:
        raise ProviderUncertain() from None


def create_params(attempt):
    return {
        "ui_mode": "elements",
        "mode": "payment",
        "payment_method_types": ["card"],
        "return_url": attempt.return_url,
        "expires_at": int(attempt.expires_at.timestamp()),
        "metadata": {
            "booking_id": str(attempt.booking_id),
            "payment_attempt_id": str(attempt.id),
        },
        "line_items": [
            {
                "price_data": {
                    "currency": "aud",
                    "unit_amount": amount,
                    "product_data": {"name": name},
                },
                "quantity": 1,
            }
            for name, amount in [
                ("Pet boarding", attempt.subtotal_cents),
                ("PAWTEL service fee", attempt.service_fee_cents),
            ]
        ],
    }


class StripeGateway:
    def __init__(self, settings: Settings):
        if not settings.stripe_secret_key or not settings.stripe_return_url:
            raise APIError(
                503, "payments_not_configured", "Sandbox payments are not configured."
            )
        self.client = stripe.StripeClient(
            settings.stripe_secret_key.get_secret_value(),
            stripe_version="2026-10-28.endive",
            max_network_retries=1,
            http_client=stripe.RequestsClient(timeout=10),
        )

    def invoke(self, call):
        try:
            return parse_session(call())
        except (
            stripe.InvalidRequestError,
            stripe.AuthenticationError,
            stripe.PermissionError,
        ):
            raise ProviderRejected() from None
        except stripe.StripeError:
            raise ProviderUncertain() from None

    def create(self, attempt):
        return self.invoke(
            lambda: self.client.v1.checkout.sessions.create(
                create_params(attempt),
                options={"idempotency_key": f"pawtel-checkout-{attempt.id}"},
            )
        )

    def retrieve(self, session_id):
        return self.invoke(
            lambda: self.client.v1.checkout.sessions.retrieve(session_id)
        )

    def expire(self, session_id):
        return self.invoke(
            lambda: self.client.v1.checkout.sessions.expire(
                session_id, options={"idempotency_key": f"pawtel-expire-{session_id}"}
            )
        )

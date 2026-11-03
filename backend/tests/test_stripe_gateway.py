from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
import stripe
from pydantic import SecretStr

from app.core.config import Settings
from app.payments.gateway import (
    ProviderRejected,
    ProviderUncertain,
    StripeGateway,
    parse_session,
)


def config(**values):
    return Settings(
        _env_file=None,
        app_env="test",
        stripe_secret_key=SecretStr("sk_test_synthetic"),
        stripe_return_url="http://localhost:5173/checkout/return",
        **values,
    )


@pytest.mark.parametrize("key", ["sk_live_synthetic", "rk_live_synthetic", "unknown"])
def test_live_keys_rejected(key):
    with pytest.raises(ValueError):
        Settings(_env_file=None, stripe_secret_key=key)


def test_secrets_redacted_and_return_url_validated():
    cfg = config()
    assert cfg.stripe_secret_key.get_secret_value() not in repr(cfg)
    with pytest.raises(ValueError):
        Settings(
            _env_file=None, stripe_return_url="https://user:pass@example.com/return"
        )


def test_sdk_stable_idempotency_and_exact_create_parameters(monkeypatch):
    gateway = StripeGateway(config())
    attempt = SimpleNamespace(
        id=uuid4(),
        booking_id=uuid4(),
        subtotal_cents=10000,
        service_fee_cents=1000,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        return_url="http://localhost:5173/checkout/return",
    )
    calls = []
    response = {
        "id": "cs_test_synthetic",
        "livemode": False,
        "mode": "payment",
        "status": "open",
        "payment_status": "unpaid",
        "amount_total": 11000,
        "currency": "aud",
        "expires_at": int(attempt.expires_at.timestamp()),
        "metadata": {
            "booking_id": str(attempt.booking_id),
            "payment_attempt_id": str(attempt.id),
        },
        "client_secret": "synthetic-secret",
    }

    def create(params, options):
        calls.append((params, options))
        return response

    monkeypatch.setattr(gateway.client.v1.checkout.sessions, "create", create)
    a = gateway.create(attempt)
    b = gateway.create(attempt)
    assert a == b and calls[0] == calls[1]
    assert calls[0][1] == {"idempotency_key": f"pawtel-checkout-{attempt.id}"}
    assert "synthetic-secret" not in repr(a)


@pytest.mark.parametrize(
    "error,expected",
    [
        (stripe.APIConnectionError("synthetic"), ProviderUncertain),
        (stripe.InvalidRequestError("synthetic", param="test"), ProviderRejected),
        (stripe.APIError("synthetic"), ProviderUncertain),
    ],
)
def test_sdk_errors_are_classified_without_leaking(error, expected):
    gateway = StripeGateway(config())

    def fail():
        raise error

    with pytest.raises(expected):
        gateway.invoke(fail)


@pytest.mark.parametrize(
    "obj",
    [
        {},
        {"livemode": True, "mode": "payment", "id": "cs_live_unsafe"},
        {"livemode": False, "mode": "subscription", "id": "cs_test_synthetic"},
    ],
)
def test_malformed_or_live_provider_responses_rejected(obj):
    with pytest.raises(ProviderUncertain):
        parse_session(obj)

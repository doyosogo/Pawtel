import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.api.v1.payments import payment_gateway
from app.models import (
    Booking,
    BookingPet,
    HostProfile,
    Listing,
    ListingAcceptedSpecies,
    PaymentAttempt,
    Pet,
    StripeWebhookEvent,
    User,
)
from app.payments import service, webhooks
from app.payments.gateway import (
    ProviderRejected,
    ProviderUncertain,
    create_params,
    parse_session,
)
from app.services import auth, bookings

pytestmark = pytest.mark.integration


class FakeGateway:
    def __init__(self, db):
        self.db = db
        self.sessions = {}
        self.creates = []
        self.params = []
        self.uncertain = False
        self.reject = False
        self.fail_expire = False

    def create(self, attempt):
        assert not self.db.in_transaction(), "Network must run outside DB transaction"
        self.creates.append(attempt.id)
        self.params.append(create_params(attempt))
        if self.reject:
            raise ProviderRejected()
        if attempt.id not in self.sessions:
            self.sessions[attempt.id] = {
                "id": "cs_test_" + uuid4().hex,
                "object": "checkout.session",
                "livemode": False,
                "mode": "payment",
                "amount_total": attempt.amount_cents,
                "currency": "aud",
                "status": "open",
                "payment_status": "unpaid",
                "expires_at": int(attempt.expires_at.timestamp()),
                "metadata": {
                    "booking_id": str(attempt.booking_id),
                    "payment_attempt_id": str(attempt.id),
                },
                "client_secret": "synthetic-client-secret-not-a-real-credential",
                "payment_intent": None,
            }
        if self.uncertain:
            self.uncertain = False
            raise ProviderUncertain()
        return parse_session(self.sessions[attempt.id])

    def retrieve(self, sid):
        assert not self.db.in_transaction()
        return parse_session(next(s for s in self.sessions.values() if s["id"] == sid))

    def expire(self, sid):
        assert not self.db.in_transaction()
        if self.fail_expire:
            raise ProviderUncertain()
        obj = next(s for s in self.sessions.values() if s["id"] == sid)
        obj["status"] = "expired"
        return parse_session(obj)


@pytest.fixture
def pay(db_session, make_api, settings, monkeypatch):
    # Existing request test Sessions bind to the same rollback connection. A provider
    # fake checks the service Session itself separately in dedicated service tests.
    settings.stripe_return_url = "http://localhost:5173/checkout/return"
    from pydantic import SecretStr

    settings.stripe_webhook_secret = SecretStr(uuid4().hex)
    owner = make_api()
    registration = owner.register(email="payment-owner@example.com")
    oid = UUID(registration.json()["user"]["id"])
    with db_session.begin():
        raw = auth.issue_verification_token(db_session, oid, settings)
    assert owner.post("/verify-email", {"token": raw}).status_code == 204
    assert owner.login(email="payment-owner@example.com").status_code == 200
    host = User(
        email="payment-host@example.test",
        display_name="Host",
        email_verified_at=datetime.now(UTC),
    )
    listing = Listing(
        host=HostProfile(user=host),
        status="PUBLISHED",
        title="Payment fixture",
        description="Synthetic stay",
        suburb="Norwood",
        state="SA",
        postcode="5067",
        max_pet_capacity=2,
        base_nightly_price_cents=5000,
        additional_pet_price_cents=1000,
        accepted_species=[ListingAcceptedSpecies(species="DOG")],
    )
    pet = Pet(owner_id=oid, name="Milo", species="DOG")
    start = datetime.now(UTC).date() + timedelta(days=10)
    booking = Booking(
        owner_id=oid,
        listing=listing,
        start_date=start,
        end_date=start + timedelta(days=2),
        status="AWAITING_PAYMENT",
        payment_expires_at=datetime.now(UTC) + timedelta(minutes=30),
        nightly_base_price_cents=5000,
        additional_pet_price_cents=1000,
        subtotal_cents=10000,
        service_fee_cents=1000,
        total_cents=11000,
        booking_pets=[BookingPet(pet=pet)],
    )
    db_session.add(booking)
    db_session.flush()
    db_session.commit()
    gateway = FakeGateway(db_session)
    # Route service uses its own Session, so bind gateway checks to the precise
    # Session passed to start/cleanup rather than the setup Session's outer savepoint.
    original_start = service.start

    def start_service(db, *args):
        gateway.db = db
        return original_start(db, *args)

    monkeypatch.setattr(service, "start", start_service)
    owner.client._transport.app.dependency_overrides[payment_gateway] = lambda: gateway

    def another_api():
        api = make_api()
        api.client._transport.app.dependency_overrides[payment_gateway] = lambda: (
            gateway
        )
        return api

    return {
        "owner": owner,
        "oid": oid,
        "booking": booking,
        "booking_id": booking.id,
        "gateway": gateway,
        "settings": settings,
        "db": db_session,
        "make_api": another_api,
    }


def checkout(p, body=None, booking_id=None, csrf=True):
    api = p["owner"]
    return asyncio.run(
        api.client.post(
            f"/api/v1/bookings/{booking_id or p['booking_id']}/checkout-session",
            json=body or {},
            headers=api.csrf() if csrf else {},
        )
    )


def payload(p, kind="checkout.session.completed", **changes):
    obj = dict(next(iter(p["gateway"].sessions.values())))
    obj.pop("client_secret", None)
    obj.update(
        status="complete" if kind.endswith("completed") else "expired",
        payment_status="paid" if kind.endswith("completed") else "unpaid",
    )
    obj.update(changes)
    return {
        "id": "evt_" + uuid4().hex,
        "object": "event",
        "livemode": False,
        "type": kind,
        "data": {"object": obj},
    }


def deliver(p, data, *, signed=True, modified=False, signature=None):
    body = json.dumps(data, separators=(",", ":")).encode()
    now = str(int(time.time()))
    secret = p["settings"].stripe_webhook_secret.get_secret_value().encode()
    digest = hmac.new(secret, now.encode() + b"." + body, hashlib.sha256).hexdigest()
    headers = (
        {"Stripe-Signature": signature or f"t={now},v1={digest}"} if signed else {}
    )
    # Clear browser headers/cookies: signature is the only credential.
    import httpx

    async def send():
        async with httpx.AsyncClient(
            transport=p["owner"].client._transport, base_url="http://testserver"
        ) as client:
            return await client.post(
                "/api/v1/webhooks/stripe",
                content=body + (b" " if modified else b""),
                headers=headers,
            )

    return asyncio.run(send())


def current(p):
    p["db"].expire_all()
    row = p["db"].get(Booking, p["booking_id"])
    attempt = p["db"].scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.booking_id == row.id)
        .order_by(
            (PaymentAttempt.status != "FAILED").desc(),
            PaymentAttempt.created_at.desc(),
            PaymentAttempt.id.desc(),
        )
    )
    return row, attempt


def test_start_uses_snapshot_reuses_secret_not_persisted(pay, caplog):
    p = pay
    p["booking"].listing.base_nightly_price_cents = 1
    p["db"].flush()
    before = datetime.now(UTC)
    response = checkout(p)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"payment_attempt_id", "client_secret", "expires_at"}
    row, attempt = current(p)
    assert attempt.amount_cents == row.total_cents == 11000
    params = p["gateway"].params[0]
    assert (
        params["ui_mode"] == "elements"
        and params["mode"] == "payment"
        and params["payment_method_types"] == ["card"]
    )
    assert sum(x["price_data"]["unit_amount"] for x in params["line_items"]) == 11000
    assert all(x["price_data"]["currency"] == "aud" for x in params["line_items"])
    assert params["metadata"] == {
        "booking_id": str(row.id),
        "payment_attempt_id": str(attempt.id),
    }
    assert (
        before + timedelta(minutes=60)
        < attempt.expires_at
        <= datetime.now(UTC) + timedelta(seconds=3660)
    )
    assert attempt.expires_at == row.payment_expires_at
    assert checkout(p).json() == response.json()
    assert len(p["gateway"].creates) == 1
    assert not hasattr(attempt, "client_secret")
    assert response.json()["client_secret"] not in caplog.text
    assert response.headers["cache-control"] == "no-store"


def test_uncertain_create_recovers_same_attempt_and_params(pay):
    p = pay
    p["gateway"].uncertain = True
    assert checkout(p).status_code == 503
    _, attempt = current(p)
    assert attempt.status == "CREATING" and attempt.checkout_session_id is None
    assert checkout(p).status_code == 200
    assert p["gateway"].creates == [attempt.id, attempt.id]
    assert p["gateway"].params[0] == p["gateway"].params[1]
    assert p["db"].scalar(select(func.count()).select_from(PaymentAttempt)) == 1


def test_db_failure_after_provider_create_recovers(pay, monkeypatch):
    original = service.record_session

    def fail(*args):
        raise RuntimeError("Synthetic local persistence failure")

    monkeypatch.setattr(service, "record_session", fail)
    assert checkout(pay).status_code == 500
    monkeypatch.setattr(service, "record_session", original)
    assert checkout(pay).status_code == 200
    assert len(set(pay["gateway"].creates)) == 1


def test_deterministic_rejection_new_attempt_no_hold_extension(pay):
    p = pay
    p["gateway"].reject = True
    assert checkout(p).status_code == 502
    _, first = current(p)
    deadline = first.expires_at
    assert first.status == "FAILED"
    p["gateway"].reject = False
    assert checkout(p).status_code == 200
    row, second = current(p)
    assert (
        second.id != first.id
        and second.expires_at == deadline == row.payment_expires_at
    )


@pytest.mark.parametrize(
    "status", ["REQUESTED", "CONFIRMED", "CANCELLED", "EXPIRED", "DECLINED"]
)
def test_wrong_booking_state_rejected(pay, status):
    p = pay
    p["booking"].status = status
    p["db"].flush()
    assert checkout(p).status_code == 409
    assert p["gateway"].creates == []


def test_closed_window_and_amount_spoof_csrf(pay):
    assert checkout(pay, {"amount_cents": 1}).status_code == 422
    assert checkout(pay, csrf=False).status_code == 403
    pay["booking"].payment_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    pay["db"].flush()
    assert checkout(pay).status_code == 409


def test_owner_scope_and_account_gates(pay):
    p = pay
    other = p["make_api"]()
    assert (
        asyncio.run(
            other.client.post(
                f"/api/v1/bookings/{p['booking_id']}/checkout-session", json={}
            )
        ).status_code
        == 401
    )
    r = other.register(email="other-payment@example.com")
    uid = UUID(r.json()["user"]["id"])
    assert other.login(email="other-payment@example.com").status_code == 200

    def send(bid):
        return asyncio.run(
            other.client.post(
                f"/api/v1/bookings/{bid}/checkout-session",
                json={},
                headers=other.csrf(),
            )
        )

    assert send(p["booking_id"]).status_code == 403
    p["db"].execute(
        update(User).where(User.id == uid).values(email_verified_at=datetime.now(UTC))
    )
    p["db"].flush()
    foreign = send(p["booking_id"])
    missing = send(uuid4())
    assert (
        foreign.status_code == missing.status_code == 404
        and foreign.json() == missing.json()
    )
    p["db"].execute(update(User).where(User.id == p["oid"]).values(is_active=False))
    p["db"].flush()
    assert checkout(p).status_code == 403


@pytest.mark.parametrize("mode", ["missing", "invalid", "modified"])
def test_signature_security(pay, mode):
    assert checkout(pay).status_code == 200
    response = deliver(
        pay,
        payload(pay),
        signed=mode != "missing",
        modified=mode == "modified",
        signature="bad" if mode == "invalid" else None,
    )
    assert response.status_code == 400
    assert current(pay)[0].status == "AWAITING_PAYMENT"
    assert pay["db"].scalar(select(func.count()).select_from(StripeWebhookEvent)) == 0


def test_paid_webhook_and_duplicate_confirm_once(pay):
    assert checkout(pay).status_code == 200
    event_data = payload(pay)
    assert deliver(pay, event_data).status_code == 200
    row, attempt = current(pay)
    assert row.status == "CONFIRMED" and attempt.status == "SUCCEEDED"
    from app.schemas.discovery import StayQuery
    from app.services.discovery import peak_occupancy

    occupancy = peak_occupancy(
        StayQuery(check_in=row.start_date, check_out=row.end_date, pet_count=1),
        row.listing_id,
    )
    assert pay["db"].scalar(select(occupancy.c.peak)) == 1
    first_time = attempt.completed_at
    assert deliver(pay, event_data).status_code == 200
    assert current(pay)[1].completed_at == first_time
    assert pay["db"].scalar(select(func.count()).select_from(StripeWebhookEvent)) == 1
    assert deliver(pay, payload(pay, "checkout.session.expired")).status_code == 200
    assert (
        current(pay)[0].status == "CONFIRMED" and current(pay)[1].status == "SUCCEEDED"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"amount_total": 1},
        {"currency": "usd"},
        {"id": "cs_test_wrong"},
        {"metadata": {"booking_id": str(uuid4()), "payment_attempt_id": "wrong"}},
        {"expires_at": 1},
    ],
)
def test_integrity_mismatches_do_not_confirm(pay, change):
    assert checkout(pay).status_code == 200
    assert deliver(pay, payload(pay, **change)).status_code == 200
    assert current(pay)[0].status == "AWAITING_PAYMENT"
    assert pay["db"].scalar(select(StripeWebhookEvent.result)) == "REJECTED"


def test_matching_attempt_wrong_booking_metadata(pay):
    assert checkout(pay).status_code == 200
    data = payload(pay)
    data["data"]["object"]["metadata"]["booking_id"] = str(uuid4())
    assert deliver(pay, data).status_code == 200
    assert current(pay)[0].status == "AWAITING_PAYMENT"
    assert current(pay)[1].status == "REQUIRES_RECONCILIATION"


def test_expiry_releases_capacity_idempotently(pay):
    assert checkout(pay).status_code == 200
    e = payload(pay, "checkout.session.expired")
    assert deliver(pay, e).status_code == 200
    row, attempt = current(pay)
    assert row.status == "EXPIRED" and attempt.status == "EXPIRED"
    assert deliver(pay, e).status_code == 200
    # Same availability algorithm observes no reserved pets after expiry.
    from app.schemas.discovery import StayQuery
    from app.services.discovery import peak_occupancy

    q = peak_occupancy(
        StayQuery(check_in=row.start_date, check_out=row.end_date, pet_count=1),
        row.listing_id,
    )
    assert pay["db"].scalar(select(q.c.peak)) is None


def test_cancel_cleanup_and_late_paid_reconciliation(pay):
    assert checkout(pay).status_code == 200
    paid = payload(pay)
    # Local cancellation commits first; no provider call under its Listing lock.
    p = pay
    p["db"].rollback()
    result = bookings.act(p["db"], p["oid"], p["booking_id"], "cancel")
    assert result.status == "CANCELLED"
    p["gateway"].db = p["db"]
    service.cleanup_cancelled(p["db"], p["booking_id"], p["gateway"])
    assert current(p)[1].status == "CANCELLED"
    assert deliver(p, paid).status_code == 200
    row, attempt = current(p)
    assert row.status == "CANCELLED" and attempt.status == "REQUIRES_RECONCILIATION"
    assert attempt.reconciliation_reason == "PAID_BOOKING_NOT_PAYABLE"


def test_cleanup_uncertainty_is_visible_and_retryable(pay):
    assert checkout(pay).status_code == 200
    p = pay
    p["gateway"].db = p["db"]
    p["db"].rollback()
    bookings.act(p["db"], p["oid"], p["booking_id"], "cancel")
    p["gateway"].fail_expire = True
    p["gateway"].db = p["db"]
    service.cleanup_cancelled(p["db"], p["booking_id"], p["gateway"])
    assert current(p)[1].reconciliation_reason == "CANCEL_CLEANUP_PENDING"
    p["db"].rollback()
    p["gateway"].fail_expire = False
    p["gateway"].db = p["db"]
    service.cleanup_cancelled(p["db"], p["booking_id"], p["gateway"])
    assert current(p)[1].status == "CANCELLED"


def test_db_webhook_failure_rolls_back_receipt_and_can_retry(pay, monkeypatch):
    assert checkout(pay).status_code == 200
    e = payload(pay)
    original = webhooks.apply_session

    def fail(*args):
        original(*args)
        raise RuntimeError("Synthetic webhook failure")

    monkeypatch.setattr(webhooks, "apply_session", fail)
    assert deliver(pay, e).status_code == 500
    assert current(pay)[0].status == "AWAITING_PAYMENT"
    assert pay["db"].scalar(select(func.count()).select_from(StripeWebhookEvent)) == 0
    monkeypatch.setattr(webhooks, "apply_session", original)
    assert deliver(pay, e).status_code == 200
    assert current(pay)[0].status == "CONFIRMED"


def test_signed_unknown_card_failure_does_not_end_open_checkout(pay):
    assert checkout(pay).status_code == 200
    data = payload(pay)
    data["type"] = "payment_intent.payment_failed"
    assert deliver(pay, data).status_code == 200
    assert (
        current(pay)[0].status == "AWAITING_PAYMENT"
        and current(pay)[1].status == "OPEN"
    )
    assert pay["db"].scalar(select(StripeWebhookEvent.result)) == "IGNORED"


def test_webhook_can_arrive_before_local_provider_write(pay, monkeypatch):
    p = pay
    original = service.record_session

    def early(db, attempt_id, session):
        e = payload(p)
        assert deliver(p, e).status_code == 200
        return original(db, attempt_id, session)

    monkeypatch.setattr(service, "record_session", early)
    assert checkout(p).status_code == 409
    assert current(p)[0].status == "CONFIRMED" and current(p)[1].status == "SUCCEEDED"


def test_malformed_provider_response_keeps_attempt_identity(pay, monkeypatch):
    def malformed(attempt):
        return parse_session({"id": "cs_test_bad", "livemode": False})

    monkeypatch.setattr(pay["gateway"], "create", malformed)
    assert checkout(pay).status_code == 503
    assert current(pay)[1].status == "CREATING"


def test_explicit_unstarted_expiry(pay):
    p = pay
    p["booking"].payment_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    p["db"].flush()
    p["db"].commit()
    assert service.expire_unstarted(p["db"], p["booking_id"])
    assert not service.expire_unstarted(p["db"], p["booking_id"])


def test_late_money_reconciliation_survives_out_of_order_expiry(pay):
    assert checkout(pay).status_code == 200
    p = pay
    p["db"].rollback()
    bookings.act(p["db"], p["oid"], p["booking_id"], "cancel")
    assert deliver(p, payload(p)).status_code == 200
    assert current(p)[1].status == "REQUIRES_RECONCILIATION"
    observed = current(p)[1].completed_at
    assert observed is not None
    assert deliver(p, payload(p, "checkout.session.expired")).status_code == 200
    assert current(p)[1].status == "REQUIRES_RECONCILIATION"
    assert current(p)[1].completed_at == observed
    assert current(p)[0].status == "CANCELLED"


def test_paid_provider_lookup_waits_for_signed_webhook(pay):
    assert checkout(pay).status_code == 200
    obj = next(iter(pay["gateway"].sessions.values()))
    obj.update(status="complete", payment_status="paid")
    assert checkout(pay).status_code == 409
    assert current(pay)[0].status == "AWAITING_PAYMENT"
    assert current(pay)[1].reconciliation_reason == "PAID_AWAITING_VERIFIED_WEBHOOK"
    assert deliver(pay, payload(pay)).status_code == 200
    assert current(pay)[0].status == "CONFIRMED"


def test_maintenance_expires_known_unpaid_checkout(pay):
    from app.payments.maintenance import reconcile

    assert checkout(pay).status_code == 200
    row, _ = current(pay)
    row.payment_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    pay["db"].commit()
    pay["gateway"].db = pay["db"]
    assert reconcile(pay["db"], pay["booking_id"], pay["gateway"]) == "EXPIRED"
    assert current(pay)[0].status == "EXPIRED"


def test_exact_webhook_exemption_does_not_weaken_browser_routes(pay):
    response = asyncio.run(
        pay["owner"].client.post(
            "/api/v1/auth/logout",
            content=b"{}",
            headers={"X-PAWTEL-Request": "", "Content-Type": "application/json"},
        )
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "request_header_required"
    response = asyncio.run(
        pay["owner"].client.post(
            "/api/v1/webhooks/other", content=b"{}", headers={"X-PAWTEL-Request": ""}
        )
    )
    assert response.status_code == 403


def test_cancel_endpoint_performs_provider_cleanup_after_commit(pay, monkeypatch):
    from pydantic import SecretStr

    from app.api.v1 import bookings as routes

    assert checkout(pay).status_code == 200
    pay["settings"].stripe_secret_key = SecretStr("sk_test_synthetic")
    monkeypatch.setattr(routes, "StripeGateway", lambda settings: pay["gateway"])
    original = service.cleanup_cancelled

    def checked_cleanup(db, bid, gateway):
        gateway.db = db
        return original(db, bid, gateway)

    monkeypatch.setattr(service, "cleanup_cancelled", checked_cleanup)
    api = pay["owner"]
    response = asyncio.run(
        api.client.post(
            f"/api/v1/bookings/{pay['booking_id']}/cancel", json={}, headers=api.csrf()
        )
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert current(pay)[1].status == "CANCELLED"


def test_zero_total_no_payment_required_confirms_only_zero(pay):
    pay["booking"].subtotal_cents = 0
    pay["booking"].service_fee_cents = 0
    pay["booking"].total_cents = 0
    pay["db"].flush()
    assert checkout(pay).status_code == 200
    assert (
        deliver(pay, payload(pay, payment_status="no_payment_required")).status_code
        == 200
    )
    assert current(pay)[0].status == "CONFIRMED"


def test_partial_unique_active_attempt_is_database_enforced(pay):
    from sqlalchemy.exc import IntegrityError

    assert checkout(pay).status_code == 200
    _, original = current(pay)
    with pytest.raises(IntegrityError), pay["db"].begin_nested():
        pay["db"].add(
            PaymentAttempt(
                booking_id=pay["booking_id"],
                amount_cents=11000,
                subtotal_cents=10000,
                service_fee_cents=1000,
                expires_at=original.expires_at,
                return_url="http://localhost:5173/checkout/return",
            )
        )
        pay["db"].flush()


def test_provider_amount_constraint_is_database_enforced(pay):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), pay["db"].begin_nested():
        pay["db"].add(
            PaymentAttempt(
                booking_id=pay["booking_id"],
                amount_cents=1,
                subtotal_cents=10000,
                service_fee_cents=1000,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                return_url="http://localhost:5173/checkout/return",
            )
        )
        pay["db"].flush()

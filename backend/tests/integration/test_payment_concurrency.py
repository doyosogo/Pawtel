"""Independent transactions prove durable concurrent webhook deduplication."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    Booking,
    HostProfile,
    Listing,
    PaymentAttempt,
    StripeWebhookEvent,
    User,
)
from app.payments.webhooks import process

pytestmark = pytest.mark.integration


def test_concurrent_duplicate_webhook_commits_one_receipt(db_engine):
    uid = uuid4()
    lid = uuid4()
    bid = uuid4()
    aid = uuid4()
    event_id = "evt_" + uuid4().hex
    sid = "cs_test_" + uuid4().hex
    now = datetime.now(UTC)
    end = (now + timedelta(hours=1)).replace(microsecond=0)
    try:
        with Session(db_engine) as setup, setup.begin():
            setup.add(
                User(
                    id=uid,
                    email=f"duplicate-{uid.hex}@example.test",
                    display_name="Synthetic",
                )
            )
            setup.flush()
            setup.add(HostProfile(user_id=uid))
            setup.flush()
            setup.add(
                Listing(
                    id=lid,
                    host_id=uid,
                    status="PUBLISHED",
                    title="Webhook fixture",
                    description="Synthetic",
                    suburb="Norwood",
                    state="SA",
                    postcode="5067",
                    max_pet_capacity=1,
                    base_nightly_price_cents=1000,
                    additional_pet_price_cents=0,
                )
            )
            setup.flush()
            setup.add(
                Booking(
                    id=bid,
                    owner_id=uid,
                    listing_id=lid,
                    status="AWAITING_PAYMENT",
                    start_date=now.date() + timedelta(days=10),
                    end_date=now.date() + timedelta(days=11),
                    payment_expires_at=end,
                    nightly_base_price_cents=1000,
                    additional_pet_price_cents=0,
                    subtotal_cents=1000,
                    service_fee_cents=100,
                    total_cents=1100,
                )
            )
            setup.flush()
            setup.add(
                PaymentAttempt(
                    id=aid,
                    booking_id=bid,
                    status="OPEN",
                    checkout_session_id=sid,
                    amount_cents=1100,
                    subtotal_cents=1000,
                    service_fee_cents=100,
                    expires_at=end,
                    return_url="http://localhost:5173/checkout/return",
                )
            )
        event = {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": sid,
                    "livemode": False,
                    "mode": "payment",
                    "status": "complete",
                    "payment_status": "paid",
                    "amount_total": 1100,
                    "currency": "aud",
                    "expires_at": int(end.timestamp()),
                    "metadata": {
                        "booking_id": str(bid),
                        "payment_attempt_id": str(aid),
                    },
                }
            },
        }
        barrier = Barrier(2)

        def worker():
            with Session(db_engine, expire_on_commit=False) as db:
                barrier.wait(timeout=5)
                process(db, event)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            for future in futures:
                future.result(timeout=10)
        with Session(db_engine) as check:
            assert check.get(Booking, bid).status == "CONFIRMED"
            assert check.get(PaymentAttempt, aid).status == "SUCCEEDED"
            assert (
                check.scalar(
                    select(func.count())
                    .select_from(StripeWebhookEvent)
                    .where(StripeWebhookEvent.id == event_id)
                )
                == 1
            )
    finally:
        with db_engine.begin() as conn:
            conn.execute(
                delete(StripeWebhookEvent).where(StripeWebhookEvent.id == event_id)
            )
            conn.execute(delete(PaymentAttempt).where(PaymentAttempt.id == aid))
            conn.execute(delete(Booking).where(Booking.id == bid))
            conn.execute(delete(Listing).where(Listing.id == lid))
            conn.execute(delete(HostProfile).where(HostProfile.user_id == uid))
            conn.execute(delete(User).where(User.id == uid))

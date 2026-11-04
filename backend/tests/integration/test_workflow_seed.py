from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.models import AuthSession, Booking, Listing, Pet, User
from app.scripts.seed_workflow import (
    HOST_EMAIL,
    HOST_ID,
    LISTING_ID,
    OWNER_EMAIL,
    OWNER_ID,
    seed_workflow_rows,
)
from app.security.credentials import new_token, token_digest, verify_password
from tests.integration.test_booking_api import request

pytestmark = pytest.mark.integration
PASSWORD = SecretStr("synthetic integration test passphrase")


def test_workflow_hashes_verifies_and_preserves_unrelated_data(db_session):
    other = User(
        email="unrelated@example.test", display_name="Unrelated", password_hash=None
    )
    db_session.add(other)
    db_session.flush()
    seed_workflow_rows(db_session, PASSWORD)
    owner = db_session.get(User, OWNER_ID)
    first_hash = owner.password_hash
    assert first_hash.startswith("$argon2id$")
    assert verify_password(PASSWORD.get_secret_value(), first_hash)
    assert owner.email_verified_at is not None
    assert db_session.get(User, HOST_ID).email_verified_at is not None
    seed_workflow_rows(db_session, PASSWORD)
    assert owner.password_hash == first_hash
    assert db_session.scalar(select(func.count()).select_from(User)) == 3
    assert db_session.scalar(select(func.count()).select_from(Pet)) == 2
    assert db_session.scalar(select(func.count()).select_from(Listing)) == 1
    assert db_session.scalar(select(func.count()).select_from(Booking)) == 0
    db_session.refresh(other)
    assert other.display_name == "Unrelated" and other.password_hash is None
    row = db_session.get(Listing, LISTING_ID)
    row.title = "Developer edited"
    seed_workflow_rows(db_session, PASSWORD)
    assert row.title == "Developer edited"


def test_workflow_password_rotation_revokes_only_demo_sessions(db_session):
    seed_workflow_rows(db_session, PASSWORD)
    now = datetime.now(UTC)
    session = AuthSession(
        user_id=OWNER_ID,
        token_digest=token_digest(new_token(), "session"),
        csrf_token=new_token(),
        expires_at=now + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.flush()
    seed_workflow_rows(db_session, SecretStr("a different synthetic test passphrase"))
    db_session.refresh(session)
    assert session.revoked_at is not None


def test_workflow_identity_collision_refuses(db_session):
    db_session.add(
        User(id=OWNER_ID, email="someone-else@example.test", display_name="Keep me")
    )
    db_session.flush()
    with pytest.raises(ValueError, match="collision"):
        seed_workflow_rows(db_session, PASSWORD)
    assert db_session.get(User, OWNER_ID).display_name == "Keep me"


def test_workflow_real_cookie_booking_roundtrip(db_session, make_api):
    seed_workflow_rows(db_session, PASSWORD)
    owner, host = make_api(), make_api()
    assert owner.login(OWNER_EMAIL, PASSWORD.get_secret_value()).status_code == 200
    assert host.login(HOST_EMAIL, PASSWORD.get_secret_value()).status_code == 200
    pets = request(owner, "GET", "/pets").json()
    assert {p["species"] for p in pets} == {"DOG", "CAT"}
    start = datetime.now(UTC).date() + timedelta(days=10)
    response = request(
        owner,
        "POST",
        "/bookings",
        {
            "listing_id": str(LISTING_ID),
            "pet_ids": [p["id"] for p in pets],
            "check_in": str(start),
            "check_out": str(start + timedelta(days=2)),
        },
    )
    assert response.status_code == 201
    booking = response.json()
    assert booking["status"] == "REQUESTED" and booking["total_cents"] == 16500
    inbox = request(host, "GET", "/host/bookings").json()
    assert len(inbox) == 1 and inbox[0]["owner_display_name"] == "Demo Owner"
    assert "email" not in inbox[0]
    accepted = request(host, "POST", f"/host/bookings/{booking['id']}/accept")
    assert (
        accepted.status_code == 200 and accepted.json()["status"] == "AWAITING_PAYMENT"
    )
    detail = request(owner, "GET", f"/bookings/{booking['id']}").json()
    assert detail["payment_expires_at"] and detail["status"] == "AWAITING_PAYMENT"

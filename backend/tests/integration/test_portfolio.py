import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.models import Booking, User
from app.scripts.seed_portfolio import seed_rows
from app.scripts.seed_workflow import OWNER_ID
from app.security.credentials import verify_password

pytestmark = pytest.mark.integration


def test_portfolio_seed_idempotent_verified_and_no_bookings(db_session):
    password = SecretStr("synthetic portfolio test passphrase")
    seed_rows(db_session, password)
    seed_rows(db_session, password)
    user = db_session.get(User, OWNER_ID)
    assert user.email_verified_at and verify_password(
        password.get_secret_value(), user.password_hash
    )
    assert db_session.scalar(select(func.count()).select_from(User)) == 2
    assert db_session.scalar(select(func.count()).select_from(Booking)) == 0


def test_portfolio_refuses_unrelated_users_without_modification(db_session):
    other = User(email="unrelated@example.test", display_name="Preserve")
    db_session.add(other)
    db_session.flush()
    with pytest.raises(ValueError, match="Unrelated"):
        seed_rows(db_session, SecretStr("synthetic portfolio test passphrase"))
    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert db_session.get(User, other.id).display_name == "Preserve"


def test_demo_registration_rejected_by_real_api(make_api):
    api = make_api()
    api.settings.portfolio_demo = True
    response = api.register()
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "demo_registration_disabled"

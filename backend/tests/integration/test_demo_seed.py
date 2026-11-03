import pytest
from sqlalchemy import func, select

from app.models import Listing, User
from app.scripts.seed_demo import STAYS, seed_rows

pytestmark = pytest.mark.integration


def test_seed_is_create_only_and_has_no_passwords(db_session):
    assert seed_rows(db_session) == len(STAYS)
    assert seed_rows(db_session) == 0
    assert db_session.scalar(select(func.count()).select_from(Listing)) == 12
    first = db_session.scalar(select(Listing).order_by(Listing.id))
    first.title = "Developer edited this stay"
    first.status = "ARCHIVED"
    db_session.flush()
    assert seed_rows(db_session) == 0
    db_session.refresh(first)
    assert first.title == "Developer edited this stay" and first.status == "ARCHIVED"
    assert not any(user.password_hash for user in db_session.scalars(select(User)))

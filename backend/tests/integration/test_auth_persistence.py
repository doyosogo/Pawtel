from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models import AuthSession, EmailVerificationToken, User
from app.security.credentials import new_token, token_digest

pytestmark = pytest.mark.integration


@pytest.fixture
def account(db_session):
    user = User(email="persistence@example.com", display_name="Persistence")
    db_session.add(user)
    db_session.flush()
    return user


def session_row(user_id, **values):
    return AuthSession(
        user_id=user_id,
        token_digest=token_digest(new_token(), "session"),
        csrf_token=new_token(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        **values,
    )


def test_session_digest_uniqueness_and_multiple_sessions(db_session, account):
    first = session_row(account.id)
    second = session_row(account.id)
    db_session.add_all([first, second])
    db_session.flush()
    duplicate = session_row(account.id)
    duplicate.token_digest = first.token_digest
    with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
        db_session.add(duplicate)
        db_session.flush()
    assert caught.value.orig.diag.constraint_name == "uq_auth_sessions_token_digest"


@pytest.mark.parametrize(
    "case, constraint",
    [
        ("digest", "ck_auth_sessions_digest_format"),
        ("expiry", "ck_auth_sessions_expiry_after_creation"),
        ("owner", "fk_auth_sessions_user_id_users"),
    ],
)
def test_session_integrity(db_session, account, case, constraint):
    row = session_row(account.id)
    if case == "digest":
        row.token_digest = "not a digest"
    elif case == "expiry":
        row.expires_at = datetime.now(UTC) - timedelta(days=1)
    else:
        row.user_id = uuid4()
    with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
        db_session.add(row)
        db_session.flush()
    assert caught.value.orig.diag.constraint_name == constraint


def test_only_one_latest_verification_row_per_user(db_session, account):
    def row():
        return EmailVerificationToken(
            user_id=account.id,
            email=account.email,
            token_digest=token_digest(new_token(), "verification"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    db_session.add(row())
    db_session.flush()
    with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
        db_session.add(row())
        db_session.flush()
    assert (
        caught.value.orig.diag.constraint_name == "uq_email_verification_tokens_user_id"
    )


def test_auth_artifacts_cascade_only_with_their_user(db_session, account):
    db_session.add(session_row(account.id))
    db_session.add(
        EmailVerificationToken(
            user_id=account.id,
            email=account.email,
            token_digest=token_digest(new_token(), "verification"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db_session.flush()
    db_session.execute(delete(User).where(User.id == account.id))
    assert db_session.scalar(select(AuthSession)) is None
    assert db_session.scalar(select(EmailVerificationToken)) is None


def test_database_rejects_plaintext_password_column(db_session):
    with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
        db_session.add(
            User(
                email="invalid@example.com",
                display_name="Invalid",
                password_hash="not a password hash",
            )
        )
        db_session.flush()
    assert caught.value.orig.diag.constraint_name == "ck_users_password_hash_algorithm"

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
import pytest
from fastapi import Depends
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.models import AuthSession, EmailVerificationToken, User
from app.security.credentials import new_token, token_digest, verify_password
from app.security.dependencies import verified_user
from app.services import auth as service

pytestmark = pytest.mark.integration
PASSWORD = "a correct ordinary passphrase"
EMAIL = "owner@example.com"


class API:
    def __init__(self, app, settings):
        self.settings = settings
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="https://api.example.com"
            if settings.session_cookie_secure
            else "http://testserver",
            headers={
                "X-PAWTEL-Request": "1",
                "Origin": settings.backend_cors_origins[0],
            },
        )

    def get(self, path, **kwargs):
        return asyncio.run(self.client.get("/api/v1/auth" + path, **kwargs))

    def post(self, path, data=None, **kwargs):
        return asyncio.run(
            self.client.post("/api/v1/auth" + path, json=data or {}, **kwargs)
        )

    def register(self, **overrides):
        return self.post(
            "/register",
            {
                "email": EMAIL,
                "display_name": "Owner",
                "password": PASSWORD,
                **overrides,
            },
        )

    def login(self, **kwargs):
        return self.post("/login", {"email": EMAIL, "password": PASSWORD}, **kwargs)

    def csrf(self):
        response = self.get("/csrf")
        assert response.status_code == 200
        return {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        app_env="test",
        session_cookie_secure=False,
        backend_cors_origins=["http://localhost:5173"],
    )


@pytest.fixture
def make_api(db_session, settings):
    clients = []

    def make(secure=False):
        config = (
            settings
            if not secure
            else Settings(
                _env_file=None,
                app_env="production",
                session_cookie_secure=True,
                backend_cors_origins=["https://app.example.com"],
            )
        )
        app = create_app(config)

        def request_db():
            # Separate per-request Session, same rollback-protected connection.
            with Session(
                bind=db_session.get_bind(),
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as session:
                yield session

        app.dependency_overrides[get_session] = request_db

        # Test-only probe for a future permission dependency, never a product API.
        @app.get("/api/v1/_test/verified")
        def verified_probe(user: Annotated[User, Depends(verified_user)]):
            return {"allowed": True}

        api = API(app, config)
        clients.append(api)
        return api

    yield make
    for api in clients:
        asyncio.run(api.client.aclose())


@pytest.fixture
def api(make_api):
    return make_api()


@pytest.fixture
def registration(db_session, settings):
    return service.register(
        db_session,
        email=EMAIL,
        display_name="Owner",
        password=PASSWORD,
        settings=settings,
    )


def rows(db, model):
    db.expire_all()
    return db.scalars(select(model)).all()


def test_registration_hashes_password_and_never_returns_secrets(api, db_session):
    response = api.register(email="  OWNER@Example.com  ")
    assert response.status_code == 201
    body = response.json()
    assert body["verification_delivery"] == "not_configured"
    assert set(body["user"]) == {
        "id",
        "email",
        "display_name",
        "email_verified_at",
        "is_active",
        "created_at",
    }
    assert body["user"]["email"] == EMAIL
    assert body["user"]["email_verified_at"] is None
    user = rows(db_session, User)[0]
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(PASSWORD, user.password_hash)
    assert PASSWORD not in vars(user).values()
    assert user.password_hash not in response.text
    assert PASSWORD not in response.text
    assert len(rows(db_session, EmailVerificationToken)) == 1
    assert not response.headers.get("set-cookie")
    assert response.headers["cache-control"] == "no-store"


def test_duplicate_email_is_consistent_and_transaction_remains_usable(api, db_session):
    assert api.register().status_code == 201
    response = api.register(email="OWNER@EXAMPLE.COM")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "registration_unavailable"
    assert len(rows(db_session, User)) == 1
    assert len(rows(db_session, EmailVerificationToken)) == 1
    assert api.register(email="other@example.com").status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"password": "short"},
        {"password": "x" * 129},
        {"display_name": " "},
        {"email": "not email"},
        {"password_hash": "not permitted"},
    ],
)
def test_validation_has_safe_consistent_errors(api, changes):
    response = api.register(**changes)
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "Invalid request data."}
    }
    assert PASSWORD not in response.text
    assert "password_hash" not in response.text


def test_wrong_and_missing_email_login_fail_identically(api):
    api.register()
    wrong = api.post("/login", {"email": EMAIL, "password": "wrong"})
    missing = api.post("/login", {"email": "absent@example.com", "password": "wrong"})
    assert wrong.status_code == missing.status_code == 401
    assert (
        wrong.json()
        == missing.json()
        == {
            "error": {
                "code": "invalid_credentials",
                "message": "Email or password is incorrect.",
            }
        }
    )
    assert "set-cookie" not in wrong.headers


def test_login_creates_digest_only_session_and_me_is_safe(api, db_session):
    api.register()
    response = api.login()
    assert response.status_code == 200
    raw = api.client.cookies.get(api.settings.session_cookie_name)
    session = rows(db_session, AuthSession)[0]
    assert session.token_digest == token_digest(raw, "session")
    assert raw not in vars(session).values()
    assert session.csrf_token != raw
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert (
        "max-age=86400" in cookie and "secure" not in cookie and "domain=" not in cookie
    )
    me = api.get("/me")
    assert me.status_code == 200 and me.json()["email_verified_at"] is None
    assert me.json() == response.json()
    assert raw not in me.text and session.token_digest not in me.text
    assert "password_hash" not in me.text and "token_digest" not in me.text
    assert me.headers["cache-control"] == "no-store"


def test_production_cookie_secure_host_only_and_csrf(make_api):
    api = make_api(secure=True)
    assert api.register().status_code == 201
    response = api.login()
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-pawtel_session=")
    assert "Secure" in cookie and "HttpOnly" in cookie and "Domain=" not in cookie
    assert api.get("/me").status_code == 200
    assert api.post("/logout", headers=api.csrf()).status_code == 204


def test_me_and_csrf_reject_missing_or_malformed_session(api):
    assert api.get("/me").status_code == 401
    assert api.get("/csrf").status_code == 401
    for raw in ["malformed", new_token()]:
        response = api.get("/me", headers={"Cookie": f"pawtel_session={raw}"})
        assert response.status_code == 401


@pytest.mark.parametrize("state", ["expired", "revoked"])
def test_dead_sessions_do_not_authenticate(api, db_session, state):
    api.register()
    api.login()
    session = rows(db_session, AuthSession)[0]
    now = datetime.now(UTC)
    changes = (
        {"created_at": now - timedelta(days=2), "expires_at": now - timedelta(days=1)}
        if state == "expired"
        else {"revoked_at": now}
    )
    db_session.execute(
        update(AuthSession).where(AuthSession.id == session.id).values(changes)
    )
    db_session.flush()
    assert api.get("/me").status_code == 401
    assert api.post("/logout").status_code == 204


def test_inactive_user_cannot_login_or_use_me_but_can_logout(api, db_session):
    api.register()
    api.login()
    db_session.execute(update(User).values(is_active=False))
    db_session.flush()
    assert api.get("/me").status_code == 403
    assert api.post("/logout", headers=api.csrf()).status_code == 204
    failed = api.login()
    assert failed.status_code == 401
    assert failed.json()["error"]["code"] == "invalid_credentials"


def test_logout_csrf_and_only_current_session_revoked(api, make_api, db_session):
    api.register()
    api.login()
    other = make_api()
    other.login()
    original = api.client.cookies.get(api.settings.session_cookie_name)
    assert len(rows(db_session, AuthSession)) == 2
    assert api.post("/logout").status_code == 403
    assert api.post("/logout", headers={"X-CSRF-Token": new_token()}).status_code == 403
    # A different authenticated session's CSRF nonce cannot authorise this one.
    assert api.post("/logout", headers=other.csrf()).status_code == 403
    assert all(row.revoked_at is None for row in rows(db_session, AuthSession))
    response = api.post("/logout", headers=api.csrf())
    assert response.status_code == 204 and "Max-Age=0" in response.headers["set-cookie"]
    assert api.get("/me").status_code == 401
    assert other.get("/me").status_code == 200
    assert api.post("/logout").status_code == 204
    assert (
        api.post(
            "/logout", headers={"Cookie": f"pawtel_session={original}"}
        ).status_code
        == 204
    )
    assert sum(row.revoked_at is not None for row in rows(db_session, AuthSession)) == 1


def test_authenticated_relogin_requires_csrf_and_rotates_current_cookie(
    api, db_session
):
    api.register()
    api.login()
    original = api.client.cookies.get(api.settings.session_cookie_name)
    assert api.login().status_code == 403
    assert api.login(headers=api.csrf()).status_code == 200
    assert api.client.cookies.get(api.settings.session_cookie_name) != original
    assert len(rows(db_session, AuthSession)) == 2
    assert sum(row.revoked_at is not None for row in rows(db_session, AuthSession)) == 1


def test_anonymous_posts_need_json_custom_header_and_trusted_origin(api):
    response = api.post(
        "/login",
        {"email": EMAIL, "password": PASSWORD},
        headers={"X-PAWTEL-Request": ""},
    )
    assert response.status_code == 403
    response = api.post("/register", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    response = asyncio.run(
        api.client.post(
            "/api/v1/auth/login",
            content="email=bad",
            headers={"Content-Type": "text/plain"},
        )
    )
    assert response.status_code == 415
    # Origin absent supports curl; the non-simple header and JSON remain required.
    api.client.headers.pop("origin")
    assert api.register().status_code == 201


def test_credentialed_cors_preflight(api):
    response = asyncio.run(
        api.client.options(
            "/api/v1/auth/logout",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "content-type,x-csrf-token,x-pawtel-request"
                ),
            },
        )
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    bad = api.post("/logout", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_verification_digest_success_and_no_reuse(api, registration, db_session):
    token = rows(db_session, EmailVerificationToken)[0]
    raw = registration.verification_token
    assert token.token_digest == token_digest(raw, "verification")
    assert raw not in vars(token).values()
    assert raw not in repr(registration)
    response = api.post("/verify-email", {"token": raw})
    assert response.status_code == 204
    assert rows(db_session, User)[0].email_verified_at is not None
    assert rows(db_session, EmailVerificationToken)[0].consumed_at is not None
    again = api.post("/verify-email", {"token": raw})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "verification_invalid"


def test_expired_and_invalid_verification_equivalent(api, registration, db_session):
    now = datetime.now(UTC)
    db_session.execute(
        update(EmailVerificationToken).values(
            created_at=now - timedelta(days=2), expires_at=now - timedelta(days=1)
        )
    )
    db_session.flush()
    expired = api.post("/verify-email", {"token": registration.verification_token})
    invalid = api.post("/verify-email", {"token": new_token()})
    assert expired.status_code == invalid.status_code == 400
    assert expired.json() == invalid.json()
    assert rows(db_session, User)[0].email_verified_at is None
    assert rows(db_session, EmailVerificationToken)[0].consumed_at is None


def test_replacement_invalidates_old_token_and_bounds_accumulation(
    api, registration, db_session, settings
):
    with db_session.begin():
        replacement = service.issue_verification_token(
            db_session, registration.user.id, settings
        )
    assert len(rows(db_session, EmailVerificationToken)) == 1
    assert (
        api.post(
            "/verify-email", {"token": registration.verification_token}
        ).status_code
        == 400
    )
    assert api.post("/verify-email", {"token": replacement}).status_code == 204


def test_verified_dependency_enforced_server_side(api, registration):
    api.login()
    response = asyncio.run(api.client.get("/api/v1/_test/verified"))
    assert (
        response.status_code == 403
        and response.json()["error"]["code"] == "email_not_verified"
    )
    assert (
        api.post(
            "/verify-email", {"token": registration.verification_token}
        ).status_code
        == 403
    )
    assert (
        api.post(
            "/verify-email",
            {"token": registration.verification_token},
            headers=api.csrf(),
        ).status_code
        == 204
    )
    assert asyncio.run(api.client.get("/api/v1/_test/verified")).status_code == 200


def test_registration_rollback_and_error_redaction(
    api, db_session, monkeypatch, caplog
):
    def fail(*args, **kwargs):
        raise RuntimeError("This deliberate test failure must not be echoed.")

    monkeypatch.setattr(service, "issue_verification_token", fail)
    response = api.register()
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert rows(db_session, User) == []
    assert rows(db_session, EmailVerificationToken) == []
    assert PASSWORD not in response.text + caplog.text
    assert "deliberate test failure" not in response.text + caplog.text


def test_verification_updates_roll_back_together(api, registration, db_session):
    def fail(mapper, connection, target):
        raise RuntimeError("deliberate failure after token UPDATE")

    event.listen(EmailVerificationToken, "after_update", fail)
    try:
        assert (
            api.post(
                "/verify-email", {"token": registration.verification_token}
            ).status_code
            == 500
        )
    finally:
        event.remove(EmailVerificationToken, "after_update", fail)
    assert rows(db_session, User)[0].email_verified_at is None
    assert rows(db_session, EmailVerificationToken)[0].consumed_at is None


def test_session_failure_does_not_set_cookie(api, db_session):
    api.register()

    def fail(mapper, connection, target):
        raise RuntimeError("deliberate session creation failure")

    event.listen(AuthSession, "before_insert", fail)
    try:
        response = api.login()
        assert response.status_code == 500 and "set-cookie" not in response.headers
    finally:
        event.remove(AuthSession, "before_insert", fail)
    assert rows(db_session, AuthSession) == []


def test_verification_is_bound_to_original_email(api, registration, db_session):
    db_session.execute(update(User).values(email="changed@example.com"))
    db_session.flush()
    response = api.post("/verify-email", {"token": registration.verification_token})
    assert response.status_code == 400
    assert rows(db_session, User)[0].email_verified_at is None
    assert rows(db_session, EmailVerificationToken)[0].consumed_at is None


def test_inactive_account_does_not_pass_verified_dependency(
    api, registration, db_session
):
    api.login()
    api.post(
        "/verify-email", {"token": registration.verification_token}, headers=api.csrf()
    )
    db_session.execute(update(User).values(is_active=False))
    db_session.flush()
    response = asyncio.run(api.client.get("/api/v1/_test/verified"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"


def test_cookie_fixation_does_not_choose_new_session(api):
    api.register()
    planted = new_token()
    response = api.login(headers={"Cookie": f"pawtel_session={planted}"})
    assert response.status_code == 200
    assert api.client.cookies.get(api.settings.session_cookie_name) != planted


def test_validation_never_echoes_raw_verification_input(api):
    supplied = "private synthetic token " * 20
    response = api.post("/verify-email", {"token": supplied})
    assert response.status_code == 422
    assert supplied not in response.text and "private synthetic" not in response.text


def test_no_email_provider_or_resend_endpoint_is_claimed(api):
    assert api.register().json()["verification_delivery"] == "not_configured"
    assert api.post("/resend-verification").status_code == 404


def test_legacy_account_with_no_hash_cannot_password_login(api, db_session):
    db_session.add(User(email=EMAIL, display_name="Legacy"))
    db_session.flush()
    assert api.login().status_code == 401
    assert rows(db_session, AuthSession) == []


def test_database_errors_do_not_log_or_serialize_secret_material(
    api, monkeypatch, caplog
):
    from sqlalchemy.exc import SQLAlchemyError

    markers = [
        PASSWORD,
        "synthetic-session-secret",
        "synthetic-verification-secret",
        "$argon2id$synthetic-hash",
    ]

    def fail(*args, **kwargs):
        raise SQLAlchemyError(" ".join(markers))

    monkeypatch.setattr(service, "issue_verification_token", fail)
    response = api.register()
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    for marker in markers:
        assert marker not in response.text + caplog.text


def test_token_replacement_rechecks_locked_user_state(
    registration, db_session, settings
):
    from sqlalchemy import text

    from app.api.errors import APIError

    # Simulate a cached User becoming stale after another writer verifies it.
    assert registration.user.email_verified_at is None
    db_session.get_bind().execute(
        text("UPDATE users SET email_verified_at = now() WHERE id = :id"),
        {"id": registration.user.id},
    )
    with pytest.raises(APIError), db_session.begin():
        service.issue_verification_token(db_session, registration.user.id, settings)
    assert len(rows(db_session, EmailVerificationToken)) == 1

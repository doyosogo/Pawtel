import asyncio

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.api.errors import APIError
from app.core.config import Settings
from app.main import create_app
from app.operations.frontend import install_frontend
from app.scripts.seed_portfolio import validate_target
from app.scripts.seed_workflow import DemoSettings
from app.services.auth import register
from tests.test_operations import production, request
from tools.deployment_smoke import check, origin


def test_managed_url_normalized_without_losing_encoded_password():
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgres://app:with%40encoding@db.example.com/pawtel?sslmode=verify-full",
    )
    assert (
        str(settings.database_url)
        == "postgresql+psycopg://app:with%40encoding@db.example.com/pawtel?sslmode=verify-full"
    )


def test_production_defaults_to_tls_and_rejects_plaintext():
    assert "sslmode=require" in str(production().database_url)
    with pytest.raises(ValidationError, match="TLS"):
        production(
            database_url="postgresql+psycopg://pawtel_app:unit-only-long-passphrase@db.example.com/pawtel?sslmode=disable"
        )


def test_demo_registration_stops_before_database_or_hash(monkeypatch):
    monkeypatch.setattr(
        "app.services.auth.hash_password",
        lambda *args: pytest.fail("Password hashing must not happen"),
    )
    with pytest.raises(APIError) as error:
        register(
            None,
            email="demo@example.com",
            display_name="Demo",
            password="unused",
            settings=Settings(_env_file=None, app_env="test", portfolio_demo=True),
        )
    assert error.value.code == "demo_registration_disabled"


def test_safe_public_configuration():
    app = create_app(Settings(_env_file=None, app_env="test", portfolio_demo=True))
    assert request(app, "/api/v1/config").json() == {
        "portfolio_demo": True,
        "registration_enabled": False,
    }


def test_static_spa_fallback_and_boundaries(tmp_path):
    (tmp_path / "index.html").write_text('<div id="root"></div>')
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app-hash.js").write_text("export {}")
    (tmp_path / ".env").write_text("never-public")
    app = create_app(Settings(_env_file=None, app_env="test"))
    install_frontend(app, tmp_path)
    for path in ("/", "/stays/123", "/account/bookings/123", "/host/listings/123/edit"):
        response = request(app, path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert 'id="root"' in response.text
    assert "immutable" in request(app, "/assets/app-hash.js").headers["cache-control"]
    for path in (
        "/.env",
        "/api/unknown",
        "/assets/missing.js",
        "/media/missing.svg",
        "/%2e%2e/secret",
    ):
        assert request(app, path).status_code == 404
    assert request(app, "/health").json() == {"status": "ok"}


def test_static_missing_build_refused(tmp_path):
    with pytest.raises(RuntimeError, match="build missing"):
        install_frontend(create_app(Settings(_env_file=None, app_env="test")), tmp_path)


def test_demo_budget_bounded_and_recovers(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.operations.demo.monotonic", lambda: now[0])
    app = create_app(Settings(_env_file=None, app_env="test", portfolio_demo=True))
    for _ in range(10):
        assert request(app, "/api/v1/auth/login", method="POST").status_code != 429
    response = request(
        app,
        "/api/v1/auth/login",
        method="POST",
        headers={"X-Forwarded-For": "different-each-time"},
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.headers["x-request-id"]
    assert request(app, "/health").status_code == 200
    now[0] += 61
    assert request(app, "/api/v1/auth/login", method="POST").status_code != 429


@pytest.mark.parametrize(
    "value",
    [
        "http://public.example.com",
        "https://user:password@example.com",
        "https://example.com?secret=hidden",
        "https://example.com/path",
    ],
)
def test_smoke_origin_rejects_unsafe_inputs(value):
    with pytest.raises(ValueError):
        origin(value)


def test_smoke_local_requires_opt_in():
    with pytest.raises(ValueError):
        origin("http://localhost:8000")
    assert origin("http://localhost:8000/", True) == "http://localhost:8000"


def test_smoke_is_read_only():
    calls = []

    def handler(req):
        calls.append(req)
        if req.url.path == "/":
            return httpx.Response(
                200, text='<div id="root"></div>', headers={"Content-Type": "text/html"}
            )
        payload = (
            {"status": "ok"}
            if req.url.path == "/health"
            else {"status": "ready"}
            if req.url.path == "/ready"
            else {"items": []}
        )
        return httpx.Response(200, json=payload, headers={"X-Request-ID": "synthetic"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert (
            len(check(client, "https://demo.example.com", "https://demo.example.com"))
            == 4
        )
    assert all(call.method == "GET" and "cookie" not in call.headers for call in calls)


def test_portfolio_seed_guards(monkeypatch):
    monkeypatch.setenv("PORTFOLIO_SEED_CONFIRM", "pawtel_portfolio")
    settings = DemoSettings(
        **production(
            database_url="postgresql://pawtel_portfolio:unit-only-long-passphrase@db.example.com/pawtel_portfolio",
            portfolio_demo=True,
        ).model_dump(),
        _env_file=None,
        pawtel_demo_password=SecretStr("synthetic private seed password"),
    )
    validate_target(settings)
    with pytest.raises(ValueError):
        validate_target(settings.model_copy(update={"portfolio_demo": False}))
    with pytest.raises(ValueError):
        validate_target(
            settings.model_copy(update={"database_url": production().database_url})
        )
    monkeypatch.delenv("PORTFOLIO_SEED_CONFIRM")
    with pytest.raises(ValueError):
        validate_target(settings)


def test_demo_auth_concurrency_bounded():
    from app.operations.demo import DemoWriteBudget

    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        count = 0
        statuses = []

        async def downstream(scope, receive, send):
            nonlocal count
            count += 1
            if count == 2:
                entered.set()
            await release.wait()

        app = DemoWriteBudget(downstream, enabled=True)

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            if message["type"] == "http.response.start":
                statuses.append(message["status"])

        scope = {"type": "http", "method": "POST", "path": "/api/v1/auth/login"}
        first = asyncio.create_task(app(scope, receive, send))
        second = asyncio.create_task(app(scope, receive, send))
        await asyncio.wait_for(entered.wait(), 1)
        await app(scope, receive, send)
        assert statuses == [429]
        release.set()
        await asyncio.gather(first, second)
        assert app.auth_inflight == 0

    asyncio.run(run())

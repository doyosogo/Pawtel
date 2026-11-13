import asyncio
import json
import logging
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.operations.http import JSON_LIMIT, correlation
from app.operations.logging import SafeJSONFormatter, request_id
from tools.e2e_data import checked_url


def configuration(**overrides):
    return Settings(
        _env_file=None,
        app_env="test",
        **{"database_url": None, "test_database_url": None, **overrides},
    )


def request(app, path="/health", **kwargs):
    async def run():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(kwargs.pop("method", "GET"), path, **kwargs)

    return asyncio.run(run())


def production(**overrides):
    values = dict(
        app_env="production",
        database_url="postgresql+psycopg://pawtel_app:unit-only-long-passphrase@db.example.com/pawtel",
        backend_cors_origins=["https://pawtel.example.com"],
        allowed_hosts=["api.example.com"],
        test_database_url=None,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_request_id_and_headers():
    ident = str(uuid4())
    response = request(create_app(configuration()), headers={"X-Request-ID": ident})
    assert response.headers["x-request-id"] == ident
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "script-src" not in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers


@pytest.mark.parametrize("supplied", [b"unsafe-token", b"", b"a" * 200, b"123\nsecret"])
def test_unsafe_correlation_replaced(supplied):
    ident = correlation([(b"x-request-id", supplied)])
    assert str(UUID(ident)) == ident


def test_duplicate_request_ids_replaced():
    ident = str(uuid4()).encode()
    assert correlation([(b"x-request-id", ident)] * 2) != ident.decode()


def test_readiness_privacy_without_database():
    app = create_app(configuration())
    assert request(app).json() == {"status": "ok"}
    response = request(app, "/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "x-request-id" in response.headers


def test_readiness_success(monkeypatch):
    monkeypatch.setattr("app.api.health.database_ready", lambda settings: True)
    response = request(create_app(configuration()), "/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_request_log_uses_template(monkeypatch):
    events = []
    monkeypatch.setattr(
        "app.operations.http.log_event", lambda *a, **k: events.append((a, k))
    )
    app = create_app(configuration())

    @app.get("/diagnostic/{identity}")
    def diagnostic(identity: str):
        return {"ok": True}

    response = request(app, "/diagnostic/private-value?token=never-log-me")
    fields = events[-1][1]
    assert fields["route"] == "/diagnostic/{identity}"
    assert fields["request_id"] == response.headers["x-request-id"]
    assert "private-value" not in str(events)
    assert "never-log-me" not in str(events)
    assert request_id.get() is None


def test_safe_correlated_exception(monkeypatch):
    events = []
    for target in ("app.operations.http.log_event", "app.security.http.log_event"):
        monkeypatch.setattr(target, lambda *a, **k: events.append((a, k)))
    app = create_app(configuration())

    @app.get("/fail")
    def fail():
        raise RuntimeError("password=never-log-me")

    response = request(app, "/fail")
    assert response.status_code == 500
    assert "never-log-me" not in response.text + str(events)
    assert "x-request-id" in response.headers
    assert any(fields.get("exception_type") == "RuntimeError" for _, fields in events)


def test_formatter_drops_secrets():
    record = logging.LogRecord(
        "pawtel", logging.ERROR, "", 0, "password=%s", ("secret",), None
    )
    record.event = "unexpected_error"
    record.exception_type = "RuntimeError"
    record.authorization = "Bearer private"
    rendered = SafeJSONFormatter().format(record)
    assert "password" not in rendered and "secret" not in rendered
    assert "authorization" not in rendered
    assert json.loads(rendered)["exception_type"] == "RuntimeError"
    record.msg = {"secret": "hidden"}
    assert "hidden" not in SafeJSONFormatter().format(record)


def test_oversized_json_cors():
    app = create_app(configuration(backend_cors_origins=["http://localhost:5173"]))
    response = request(
        app,
        "/api/v1/auth/login",
        method="POST",
        content=b"x" * (JSON_LIMIT + 1),
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.json()["error"]["code"] == "request_too_large"


def test_streamed_json_limit():
    async def run():
        async def body():
            yield b"x" * JSON_LIMIT
            yield b"x"

        async with AsyncClient(
            transport=ASGITransport(app=create_app(configuration())),
            base_url="http://test",
        ) as client:
            return await client.post("/api/v1/auth/login", content=body())

    assert asyncio.run(run()).status_code == 413


@pytest.mark.parametrize(
    "overrides",
    [
        {"session_cookie_secure": False},
        {"debug": True},
        {"allowed_hosts": []},
        {"allowed_hosts": ["*"]},
        {"backend_cors_origins": ["https://localhost"]},
        {"backend_cors_origins": ["https://127.0.0.1"]},
        {"backend_cors_origins": ["*"]},
        {
            "database_url": "postgresql+psycopg://pawtel_test:unit-only-long-passphrase@db.example.com/pawtel_test"
        },
        {
            "database_url": "postgresql+psycopg://pawtel_app:replace-me@db.example.com/pawtel"
        },
        {"stripe_secret_key": "sk_test_placeholder"},
        {"cloudinary_cloud_name": "placeholder"},
    ],
)
def test_unsafe_production_refused(overrides):
    with pytest.raises(ValidationError):
        production(**overrides)


def test_optional_providers_disabled():
    settings = production()
    assert settings.stripe_secret_key is None
    assert settings.cloudinary_api_secret is None


def test_startup_refuses_old_schema_and_disposes(monkeypatch):
    disposed = []
    events = []
    monkeypatch.setattr(
        "app.main.log_event", lambda event, **kwargs: events.append(event)
    )
    monkeypatch.setattr("app.main.database_ready", lambda settings: False)
    monkeypatch.setattr("app.main.dispose_engine", lambda: disposed.append(True))
    app = create_app(production())

    async def run():
        async with app.router.lifespan_context(app):
            pytest.fail("Must refuse startup")

    with pytest.raises(RuntimeError, match="Schema not ready"):
        asyncio.run(run())
    assert disposed == [True]
    assert events == ["startup_not_ready", "shutdown_complete"]


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://pawtel_dev:password@localhost/pawtel_dev",
        "postgresql+psycopg://pawtel_e2e:password@remote.example.com/pawtel_e2e",
        "postgresql+psycopg://pawtel_e2e:password@localhost/pawtel_e2e?host=remote.example.com",
    ],
)
def test_e2e_database_guard(monkeypatch, url):
    monkeypatch.setenv("APP_ENV", "test")
    with pytest.raises(ValueError):
        checked_url(url)


def test_e2e_production_guard(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValueError):
        checked_url("postgresql+psycopg://pawtel_e2e:password@localhost/pawtel_e2e")


def test_readiness_database_exception_is_private(monkeypatch):
    from app.operations.database import database_ready

    class FailingEngine:
        disposed = False

        def connect(self):
            raise RuntimeError("postgresql://password@host/private SQL")

        def dispose(self):
            self.disposed = True

    engine = FailingEngine()
    events = []
    monkeypatch.setattr("app.operations.database.create_engine", lambda *a, **k: engine)
    monkeypatch.setattr(
        "app.operations.database.log_event", lambda *a, **k: events.append((a, k))
    )
    assert (
        database_ready(
            configuration(
                database_url="postgresql+psycopg://unit:unit@localhost/pawtel_test"
            )
        )
        is False
    )
    assert engine.disposed
    assert events == [(("readiness_failed",), {"exception_type": "RuntimeError"})]


def test_readiness_requires_exact_heads(monkeypatch):
    from app.operations.database import database_ready

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            pass

        def scalars(self, statement):
            return ["old-revision"]

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(
        "app.operations.database.create_engine", lambda *a, **k: Engine()
    )
    monkeypatch.setattr(
        "app.operations.database.expected_heads", lambda: {"new-revision"}
    )
    assert not database_ready(
        configuration(
            database_url="postgresql+psycopg://unit:unit@localhost/pawtel_test"
        )
    )


def test_production_host_and_hsts():
    app = create_app(production())
    rejected = request(app)
    assert rejected.status_code == 400
    response = request(app, headers={"Host": "api.example.com"})
    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_formatter_suppresses_exception_values():
    import sys

    try:
        raise RuntimeError("sk_test_private_client_secret=not-for-logs")
    except RuntimeError:
        record = logging.LogRecord(
            "uvicorn.error",
            logging.ERROR,
            "",
            0,
            "error %s",
            ("private",),
            sys.exc_info(),
        )
    rendered = SafeJSONFormatter().format(record)
    assert "sk_test_private" not in rendered
    assert "client_secret" not in rendered
    assert "RuntimeError" in rendered


def test_request_context_reaches_nested_events(monkeypatch):
    from app.operations.logging import log_event

    records = []
    monkeypatch.setattr(
        logging.getLogger("pawtel"),
        "log",
        lambda *a, **k: records.append((request_id.get(), k)),
    )
    app = create_app(configuration())

    @app.get("/nested")
    def nested():
        log_event("unexpected_error", exception_type="Synthetic")
        return {"ok": True}

    response = request(app, "/nested")
    assert records
    assert {ident for ident, _ in records} == {response.headers["x-request-id"]}
    assert request_id.get() is None


def test_production_unexpected_error_is_generic_correlated_and_redacted():
    import io

    from app.operations.logging import SafeJSONFormatter

    app = create_app(production())
    canary = "private-error-canary-password-cookie-client-secret-db-url"

    @app.get("/api/v1/_test/unexpected")
    def unexpected():
        raise RuntimeError(canary)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SafeJSONFormatter())
    logger = logging.getLogger("pawtel")
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        response = request(
            app,
            "/api/v1/_test/unexpected?private=" + canary,
            headers={"Host": "api.example.com", "Cookie": "private=" + canary},
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "The request could not be completed.",
        }
    }
    reference = response.headers["x-request-id"]
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert records and all(record["request_id"] == reference for record in records)
    assert any(record.get("exception_type") == "RuntimeError" for record in records)
    assert any(record.get("route") == "/api/v1/_test/unexpected" for record in records)
    assert canary not in response.text + stream.getvalue()
    assert "traceback" not in response.text.lower()
    assert "sql" not in response.text.lower()

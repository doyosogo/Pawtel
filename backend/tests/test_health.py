import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.main import app, create_app


def test_health_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()

    def fail_on_connection(*args, **kwargs):
        raise AssertionError("Startup and health must not connect to PostgreSQL")

    monkeypatch.setattr(Engine, "connect", fail_on_connection)

    async def check():
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health")
                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
                assert get_engine.cache_info().currsize == 0

    try:
        asyncio.run(check())
    finally:
        get_settings.cache_clear()


def test_frontend_cors():
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            session_cookie_secure=False,
            backend_cors_origins=["http://localhost:5173"],
        )
    )

    async def check():
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.options(
                    "/health",
                    headers={
                        "Origin": "http://localhost:5173",
                        "Access-Control-Request-Method": "GET",
                    },
                )
                assert response.status_code == 200
                assert response.headers["access-control-allow-origin"] == (
                    "http://localhost:5173"
                )
                response = await client.get(
                    "/health", headers={"Origin": "https://untrusted.example"}
                )
                assert "access-control-allow-origin" not in response.headers

    asyncio.run(check())

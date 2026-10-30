import asyncio
from pathlib import Path
from typing import Annotated

import pytest
from alembic.config import Config
from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.models import User
from app.security.dependencies import verified_user
from tests.db_safety import checked_test_url
from tests.integration.api_client import API


@pytest.fixture(scope="session")
def db_engine():
    settings = Settings()
    try:
        url = checked_test_url(
            str(settings.test_database_url) if settings.test_database_url else None,
            str(settings.database_url) if settings.database_url else None,
        )
    except ValueError as error:
        pytest.fail(str(error), pytrace=False)
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            identity = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "current_setting('server_version_num')::integer"
                )
            ).one()
            if identity[:2] != ("pawtel_test", "pawtel_test"):
                pytest.fail(
                    "Unexpected test database/server role; refusing migrations."
                )
            if not 180000 <= identity[2] < 190000:
                pytest.fail("Integration tests require PostgreSQL 18 stable.")
            if connection.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            ):
                pytest.fail("Integration tests must not run with a superuser role.")
        # Run the real migration, never create_all: tests exercise deployed DDL.
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


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

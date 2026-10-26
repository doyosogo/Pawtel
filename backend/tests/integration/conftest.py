from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from tests.db_safety import checked_test_url


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

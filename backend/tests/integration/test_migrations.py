from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

pytestmark = pytest.mark.integration

TABLES = {
    "users",
    "auth_sessions",
    "email_verification_tokens",
    "host_profiles",
    "pets",
    "listings",
    "listing_accepted_species",
    "bookings",
    "booking_pets",
}
ENUMS = {"pet_species", "australian_state", "listing_status", "booking_status"}


def test_migration_downgrade_upgrade_on_empty_test_database(db_engine):
    # db_engine has already validated the target name, role, host and PostgreSQL 18.
    inspector = inspect(db_engine)
    assert set(inspector.get_table_names()) == TABLES | {"alembic_version"}
    with db_engine.connect() as connection:
        for table in sorted(TABLES):
            # Names are static constants, never supplied by a caller.
            if connection.scalar(text(f'SELECT EXISTS (SELECT 1 FROM "{table}")')):
                pytest.fail(
                    "Test database contains rows; refusing migration round trip."
                )
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["database_url"] = db_engine.url
    legacy_id = None
    try:
        # New auth revision can be removed without changing the Milestone 2 schema.
        command.downgrade(config, "6667e668c806")
        assert "password_hash" not in {
            column["name"] for column in inspect(db_engine).get_columns("users")
        }
        with db_engine.begin() as connection:
            legacy_id = connection.scalar(
                text(
                    "INSERT INTO users (email, display_name) "
                    "VALUES ('migration-legacy@example.com', 'Legacy') RETURNING id"
                )
            )
        command.upgrade(config, "head")
        with db_engine.begin() as connection:
            assert connection.scalar(
                text("SELECT password_hash IS NULL FROM users WHERE id = :id"),
                {"id": legacy_id},
            )
            connection.execute(
                text("DELETE FROM users WHERE id = :id"), {"id": legacy_id}
            )
        legacy_id = None
        command.downgrade(config, "base")
        inspector = inspect(db_engine)
        assert set(inspector.get_table_names()) == {"alembic_version"}
        assert not {item["name"] for item in inspector.get_enums()} & ENUMS
    finally:
        command.upgrade(config, "head")
        if legacy_id is not None:
            with db_engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM users WHERE id = :id"), {"id": legacy_id}
                )
    inspector = inspect(db_engine)
    assert set(inspector.get_table_names()) == TABLES | {"alembic_version"}
    assert {item["name"] for item in inspector.get_enums()} == ENUMS
    command.check(config)

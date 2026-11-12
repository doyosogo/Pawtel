"""Explicit pre-test migration, using the same destructive-test target guards."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import Settings
from tests.db_safety import checked_test_url


def main():
    settings = Settings()
    url = checked_test_url(
        str(settings.test_database_url) if settings.test_database_url else None,
        str(settings.database_url) if settings.database_url else None,
    )
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "current_setting('server_version_num')::int, "
                    "(SELECT rolsuper FROM pg_roles WHERE rolname=current_user)"
                )
            ).one()
            if (
                row[:2] != ("pawtel_test", "pawtel_test")
                or row[3]
                or not 180000 <= row[2] < 190000
            ):
                raise RuntimeError("Refusing unexpected migration target.")
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool, text

from app.operations.logging import log_event


@lru_cache
def expected_heads():
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "alembic")
    )
    return set(ScriptDirectory.from_config(config).get_heads())


def database_ready(settings):
    if not settings.database_url:
        return False
    engine = create_engine(
        str(settings.database_url),
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={"connect_timeout": 2},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SET statement_timeout = '1000ms'"))
            connection.execute(text("SELECT 1"))
            return (
                set(connection.scalars(text("SELECT version_num FROM alembic_version")))
                == expected_heads()
            )
    except Exception as error:
        log_event("readiness_failed", exception_type=type(error).__name__)
        return False
    finally:
        engine.dispose()

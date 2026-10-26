from sqlalchemy import URL, create_engine, pool

from alembic import context
from app import models  # noqa: F401 -- register all model metadata
from app.core.config import get_settings
from app.db.base import Base


def database_url() -> str | URL:
    url = context.config.attributes.get("database_url") or get_settings().database_url
    if url is None:
        raise RuntimeError("Set DATABASE_URL before running migrations.")
    return url if isinstance(url, URL) else str(url)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        database_url(), poolclass=pool.NullPool, hide_parameters=True
    )
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

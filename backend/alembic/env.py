from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine


def database_url() -> str:
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("Set DATABASE_URL before running migrations.")
    return str(url)


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
    engine = get_engine()
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

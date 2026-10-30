from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create the engine lazily; opening a session establishes the connection."""
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("Set DATABASE_URL before using database operations.")
    return create_engine(str(url), pool_pre_ping=True, hide_parameters=True)


def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
        get_engine.cache_clear()


def get_session() -> Iterator[Session]:
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session

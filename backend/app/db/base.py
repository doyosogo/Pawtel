from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared migration metadata; domain models will be added later."""

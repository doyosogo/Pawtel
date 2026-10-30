from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    app_name: str = "PAWTEL API"
    app_env: Literal["development", "test", "production"] = "production"
    database_url: PostgresDsn | None = None
    test_database_url: PostgresDsn | None = None
    backend_cors_origins: list[str] = []
    session_cookie_secure: bool = True
    session_lifetime_seconds: int = Field(default=86400, ge=300, le=604800)
    verification_lifetime_seconds: int = Field(default=86400, ge=300, le=172800)

    @model_validator(mode="after")
    def validate_security(self):
        if self.app_env == "production" and not self.session_cookie_secure:
            raise ValueError("Production requires Secure session cookies.")
        for origin in self.backend_cors_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError("CORS requires exact HTTP(S) origins without paths.")
            if self.app_env == "production" and parsed.scheme != "https":
                raise ValueError("Production CORS origins must use HTTPS.")
        return self

    @property
    def session_cookie_name(self) -> str:
        return (
            "__Host-pawtel_session" if self.session_cookie_secure else "pawtel_session"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

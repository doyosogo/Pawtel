from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    app_name: str = "PAWTEL API"
    app_env: Literal["development", "test", "production"] = "production"
    stripe_secret_key: SecretStr | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_return_url: str | None = None
    database_url: PostgresDsn | None = None
    test_database_url: PostgresDsn | None = None
    backend_cors_origins: list[str] = []
    session_cookie_secure: bool = True
    session_lifetime_seconds: int = Field(default=86400, ge=300, le=604800)
    booking_payment_window_seconds: int = Field(default=1800, ge=60, le=86400)
    verification_lifetime_seconds: int = Field(default=86400, ge=300, le=172800)

    @model_validator(mode="after")
    def validate_security(self):
        if (
            self.stripe_secret_key
            and not self.stripe_secret_key.get_secret_value().startswith(
                ("sk_test_", "rk_test_", "rkcs_test_")
            )
        ):
            raise ValueError("Only Stripe sandbox/test keys are permitted.")
        if self.stripe_publishable_key and not self.stripe_publishable_key.startswith(
            "pk_test_"
        ):
            raise ValueError("Only Stripe test publishable keys are permitted.")
        if self.stripe_return_url:
            returned = urlsplit(self.stripe_return_url)
            if (
                returned.scheme not in {"http", "https"}
                or not returned.hostname
                or returned.username
                or returned.password
                or returned.query
                or returned.fragment
            ):
                raise ValueError(
                    "Use a plain HTTP(S) Stripe return URL without credentials/query."
                )
            if self.app_env == "production" and returned.scheme != "https":
                raise ValueError("Production return URL requires HTTPS.")
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

import ipaddress
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: SecretStr | None = None
    cloudinary_api_secret: SecretStr | None = None
    allowed_hosts: list[str] = []
    debug: bool = False
    serve_frontend: bool = False
    portfolio_demo: bool = False
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

    @field_validator("database_url", mode="before")
    @classmethod
    def managed_database_url(cls, value):
        if isinstance(value, str):
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value[len(prefix) :]
        return value

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
        if self.app_env == "production":
            self.validate_production()
        return self

    def validate_production(self):
        def local(host):
            if (
                not host
                or host == "localhost"
                or host.endswith((".localhost", ".local"))
            ):
                return True
            try:
                return (
                    ipaddress.ip_address(host).is_loopback
                    or ipaddress.ip_address(host).is_unspecified
                )
            except ValueError:
                return False

        def placeholder(value):
            return any(
                word in value.lower()
                for word in ("replace", "changeme", "placeholder", "synthetic")
            )

        if (
            self.debug
            or not self.database_url
            or not self.backend_cors_origins
            or not self.allowed_hosts
        ):
            raise ValueError(
                "Production requires database, origins/hosts and debug disabled."
            )
        url = make_url(str(self.database_url))
        if "sslmode" not in url.query:
            url = url.update_query_dict({"sslmode": "require"})
            self.database_url = PostgresDsn(url.render_as_string(hide_password=False))
        if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("Production database connections require TLS.")
        if (
            url.drivername != "postgresql+psycopg"
            or not url.database
            or not url.username
            or re.search(r"(^|_)(test|dev|e2e)($|_)", url.database or "", re.I)
            or url.username == "postgres"
        ):
            raise ValueError(
                "Production requires a non-test database and application role."
            )
        if not url.password or len(url.password) < 16 or placeholder(url.password):
            raise ValueError(
                "Production requires a non-placeholder database credential."
            )
        if self.test_database_url:
            raise ValueError("Do not configure the test database in production.")
        if any(
            local(urlsplit(origin).hostname) for origin in self.backend_cors_origins
        ):
            raise ValueError("Production origins cannot be local development hosts.")
        if any(
            local(host) or not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "*" in host
            for host in self.allowed_hosts
        ):
            raise ValueError(
                "Production allowed_hosts must be explicit non-local hostnames."
            )
        stripe = [
            self.stripe_secret_key,
            self.stripe_webhook_secret,
            self.stripe_return_url,
        ]
        if any(stripe):
            if not all(stripe):
                raise ValueError(
                    "Payments require API key, webhook secret and return URL."
                )
            if any(
                len(secret.get_secret_value()) < 32
                or placeholder(secret.get_secret_value())
                for secret in stripe[:2]
            ):
                raise ValueError(
                    "Configured payments require non-placeholder credentials."
                )
            if not self.stripe_webhook_secret.get_secret_value().startswith("whsec_"):
                raise ValueError(
                    "Configured payments require a webhook signing secret."
                )
        cloud = [
            self.cloudinary_cloud_name,
            self.cloudinary_api_key,
            self.cloudinary_api_secret,
        ]
        if any(cloud):
            if not all(cloud) or not re.fullmatch(
                r"[A-Za-z0-9_-]+", self.cloudinary_cloud_name or ""
            ):
                raise ValueError(
                    "Configured media requires complete Cloudinary settings."
                )
            if (
                any(
                    placeholder(secret.get_secret_value())
                    or len(secret.get_secret_value()) < 10
                    for secret in cloud[1:]
                )
                or len(self.cloudinary_api_secret.get_secret_value()) < 20
            ):
                raise ValueError(
                    "Configured media requires non-placeholder credentials."
                )

    @property
    def session_cookie_name(self) -> str:
        return (
            "__Host-pawtel_session" if self.session_cookie_secure else "pawtel_session"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

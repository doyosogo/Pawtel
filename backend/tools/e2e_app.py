"""Test-runner-only app factory: real routes/DB, no provider credentials or bypasses."""

import os

from app.core.config import Settings
from app.main import create_app
from tools.e2e_data import checked_url


def create_e2e_app():
    url = checked_url(os.environ.get("E2E_DATABASE_URL"))
    return create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url=url.render_as_string(hide_password=False),
            test_database_url=None,
            session_cookie_secure=False,
            backend_cors_origins=["http://127.0.0.1:4173"],
            stripe_secret_key=None,
            stripe_webhook_secret=None,
            cloudinary_api_key=None,
            cloudinary_api_secret=None,
        )
    )

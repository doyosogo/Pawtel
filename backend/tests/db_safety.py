from sqlalchemy.engine import URL, make_url


def checked_test_url(value: str | None, development_url: str | None) -> URL:
    """Validate the target before connecting, migrating or opening test transactions."""
    if not value:
        raise ValueError("Set TEST_DATABASE_URL, or run pytest -m 'not integration'.")
    url = make_url(value)
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "pawtel_test"
        or url.username != "pawtel_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError(
            "Tests require a local pawtel_test database and pawtel_test role."
        )
    # Reject libpq options which could override the already validated target.
    if url.query:
        raise ValueError("TEST_DATABASE_URL must not contain connection query options.")
    if development_url:
        dev = make_url(development_url)
        if dev.database == url.database:
            raise ValueError("Development and test databases must be different.")
    return url

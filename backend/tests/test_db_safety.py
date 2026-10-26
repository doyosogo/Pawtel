import pytest

from tests.db_safety import checked_test_url


@pytest.mark.parametrize(
    "url",
    [
        None,
        "postgresql+psycopg://pawtel_dev@localhost/pawtel_dev",
        "postgresql+psycopg://pawtel_test@example.com/pawtel_test",
        "postgresql+psycopg://postgres@localhost/pawtel_test",
        "sqlite:///pawtel_test",
        "postgresql+psycopg://pawtel_test@localhost/pawtel_test?dbname=pawtel_dev",
    ],
)
def test_unsafe_integration_targets_rejected(url):
    with pytest.raises(ValueError):
        checked_test_url(url, None)


def test_development_database_must_be_distinct():
    url = "postgresql+psycopg://pawtel_test@localhost/pawtel_test"
    with pytest.raises(ValueError, match="must be different"):
        checked_test_url(url, url)


def test_dedicated_local_test_target_allowed():
    url = "postgresql+psycopg://pawtel_test@127.0.0.1:5433/pawtel_test"
    assert checked_test_url(url, None).database == "pawtel_test"

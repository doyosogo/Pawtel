import pytest

from app.core.config import Settings
from app.scripts.seed_demo import validate_target


@pytest.mark.parametrize(
    "environment,url",
    [
        ("production", "postgresql+psycopg://pawtel_dev@localhost/pawtel_dev"),
        ("development", "postgresql+psycopg://pawtel_dev@remote.example/pawtel_dev"),
        ("development", "postgresql+psycopg://pawtel_test@localhost/pawtel_test"),
        (
            "development",
            "postgresql+psycopg://pawtel_dev@localhost/pawtel_dev?options=x",
        ),
    ],
)
def test_seed_refuses_unsafe_target(environment, url):
    with pytest.raises(ValueError):
        validate_target(Settings(_env_file=None, app_env=environment, database_url=url))

import pytest
from pydantic import SecretStr

from app.scripts.seed_workflow import DemoSettings, main, run, validate_password


def test_workflow_refuses_production_before_connecting(monkeypatch):
    monkeypatch.setattr(
        "app.scripts.seed_workflow.get_engine", lambda: pytest.fail("DB access")
    )
    with pytest.raises(ValueError, match="development"):
        run(DemoSettings(_env_file=None, app_env="production"))


@pytest.mark.parametrize("password", [None, SecretStr("short")])
def test_workflow_requires_explicit_passphrase(password):
    with pytest.raises(ValueError, match="PAWTEL_DEMO_PASSWORD"):
        validate_password(password)


def test_workflow_errors_do_not_leak_secrets(monkeypatch, capsys):
    def fail(_):
        raise ValueError("synthetic-secret-that-must-not-be-logged")

    monkeypatch.setattr("app.scripts.seed_workflow.run", fail)
    with pytest.raises(SystemExit):
        main()
    assert "synthetic-secret-that-must-not-be-logged" not in capsys.readouterr().out

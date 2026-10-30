import pytest
from argon2 import Type
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.auth import RegisterInput
from app.security.credentials import (
    PASSWORD_HASHER,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)


def test_argon2id_and_password_verification():
    password = "a long ordinary passphrase"
    encoded = hash_password(password)
    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert PASSWORD_HASHER.type is Type.ID
    assert PASSWORD_HASHER.memory_cost == 65536
    assert verify_password(password, encoded)
    assert not verify_password("wrong password", encoded)
    assert not verify_password(password, None)
    assert not verify_password(password, "$argon2id$malformed")


def test_random_tokens_and_purpose_separation():
    raw = new_token()
    assert len(raw) == 43
    assert new_token() != raw
    assert len(token_digest(raw, "session")) == 64
    assert token_digest(raw, "session") != token_digest(raw, "verification")
    assert raw not in token_digest(raw, "session")


@pytest.mark.parametrize(
    "password",
    ["x" * 15, "x" * 128, "all lowercase long words", " space padded passphrase "],
)
def test_passphrase_friendly_policy(password):
    body = RegisterInput(
        email="User@Example.com", display_name=" Name ", password=password
    )
    assert body.password.get_secret_value() == password
    assert body.email == "user@example.com"
    assert body.display_name == "Name"
    assert password not in repr(body)


@pytest.mark.parametrize("password", ["x" * 14, "x" * 129, ""])
def test_registration_password_bounds(password):
    with pytest.raises(ValidationError):
        RegisterInput(email="user@example.com", display_name="Name", password=password)


def test_production_fails_closed_on_insecure_config():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", session_cookie_secure=False)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            backend_cors_origins=["http://localhost:5173"],
        )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="test", backend_cors_origins=["*"])
    settings = Settings(_env_file=None)
    assert settings.session_cookie_secure
    assert settings.session_cookie_name == "__Host-pawtel_session"
    assert settings.backend_cors_origins == []


def test_missing_hash_performs_dummy_verification(monkeypatch):
    from app.security import credentials

    calls = []

    class Verifier:
        def verify(self, encoded, password):
            calls.append(encoded == credentials.DUMMY_HASH)
            return True

    monkeypatch.setattr(credentials, "PASSWORD_HASHER", Verifier())
    assert not credentials.verify_password("nonexistent account password", None)
    assert calls == [True]

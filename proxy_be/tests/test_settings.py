"""Tests for backend configuration."""

import pytest
from pydantic import ValidationError

from proxy_be.settings import Settings

REQUIRED = {
    "GITHUB_TOKEN": "ghp_example",
    "TOKEN_SECRET": "token-secret-value",
    "USER_KEY_SECRET": "user-key-secret-value",
}


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    settings = Settings()
    assert settings.github_repo == "gh-workflow-fiesta"
    assert settings.github_ref == "dev"
    assert settings.leg_timeout_seconds == 300


def test_secrets_are_not_exposed_by_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    settings = Settings()
    assert "ghp_example" not in repr(settings)
    assert settings.github_token.get_secret_value() == "ghp_example"


def test_missing_secrets_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_timeout_bounds_are_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("LEG_TIMEOUT_SECONDS", "9999")
    with pytest.raises(ValidationError):
        Settings()

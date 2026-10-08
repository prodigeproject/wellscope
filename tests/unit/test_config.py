from __future__ import annotations

from pathlib import Path

import pytest

from wellscope.config import Settings


def make_settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_settings_use_safe_defaults_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = make_settings()
    assert settings.host == "127.0.0.1"
    assert settings.openai_api_key is None
    assert settings.database_path == Path("data/processed/wellscope.db")


def test_settings_read_standard_openai_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-" + "a" * 32
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    settings = make_settings()
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == secret


def test_settings_never_expose_the_key_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-" + "b" * 32
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    assert secret not in repr(make_settings())


def test_settings_reject_out_of_range_limits() -> None:
    with pytest.raises(ValueError, match="max_question_chars"):
        make_settings(max_question_chars=10)

from __future__ import annotations

from uagent.env_validate import validate_startup_env


def test_lmstudio_does_not_require_api_key(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "lmstudio")
    monkeypatch.delenv("UAGENT_LMSTUDIO_API_KEY", raising=False)

    provider, missing, warnings = validate_startup_env()

    assert provider == "lmstudio"
    assert not any(item.name == "UAGENT_LMSTUDIO_API_KEY" for item in missing)
    assert not warnings


def test_inception_accepts_official_api_key_name(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "inception")
    monkeypatch.delenv("UAGENT_INCEPTION_API_KEY", raising=False)
    monkeypatch.setenv("INCEPTION_API_KEY", "test-key")

    provider, missing, warnings = validate_startup_env()

    assert provider == "inception"
    assert not any(item.name == "UAGENT_INCEPTION_API_KEY" for item in missing)
    assert not warnings


def test_ollama_does_not_require_api_key(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "ollama")
    monkeypatch.delenv("UAGENT_OLLAMA_API_KEY", raising=False)

    provider, missing, warnings = validate_startup_env()

    assert provider == "ollama"
    assert not any(item.name == "UAGENT_OLLAMA_API_KEY" for item in missing)
    assert not warnings

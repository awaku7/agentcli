from __future__ import annotations

from uagent.env_validate import validate_startup_env


def test_lmstudio_does_not_require_api_key(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "lmstudio")
    monkeypatch.delenv("UAGENT_LMSTUDIO_API_KEY", raising=False)

    provider, missing, warnings = validate_startup_env()

    assert provider == "lmstudio"
    assert not any(item.name == "UAGENT_LMSTUDIO_API_KEY" for item in missing)
    assert not warnings

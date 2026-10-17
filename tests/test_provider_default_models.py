"""Default model IDs stay aligned with the providers' current model aliases."""

from __future__ import annotations

import pytest

from uagent.providers.util_providers import get_model_name


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("grok", "grok-4.7"),
        ("zai", "glm-5.3"),
        ("alibaba", "qwen3.7-plus"),
        ("sarashina", "sarashina3-mini"),
        ("moonshot", "kimi-k3"),
    ],
)
def test_current_provider_default_models(
    monkeypatch, provider: str, expected: str
) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", provider)
    monkeypatch.delenv(f"UAGENT_{provider.upper()}_DEPNAME", raising=False)

    assert get_model_name() == expected


def test_provider_model_override_is_preserved(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_PROVIDER", "moonshot")
    monkeypatch.setenv("UAGENT_MOONSHOT_DEPNAME", "custom-model-id")

    assert get_model_name() == "custom-model-id"

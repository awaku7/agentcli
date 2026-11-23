"""Default model IDs stay aligned with the providers' current model aliases."""

from __future__ import annotations

import pytest

from uagent.providers.util_providers import get_model_name


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("azure", "gpt-6.2-sol"),
        ("bedrock", "openai.gpt-oss-120b"),
        ("openai", "gpt-6-luna"),
        ("openrouter", "openai/gpt-6-luna"),
        ("claude", "claude-sonnet-5-5"),
        ("grok", "grok-4.7"),
        ("gemini", "gemini-4-hydrogen"),
        ("vertexai", "gemini-4-hydrogen"),
        ("deepseek", "deepseek-flash"),
        ("inception", "mercury-3"),
        ("zai", "glm-5.3"),
        ("alibaba", "qwen3.7-plus"),
        ("moonshot", "kimi-k3.1-pro"),
        ("mimo", "mimo-v2.6-pro"),
        ("novita", "tencent/hy3"),
        ("sarashina", "sarashina3.2-mini-thinking"),
        ("vercel", "openai/gpt-6-luna"),
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

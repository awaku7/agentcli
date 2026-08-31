from __future__ import annotations

from uagent.i18n import set_thread_lang
from uagent.util_model import _append_resolved_model_section


def _render(provider: str) -> list[str]:
    lines: list[str] = []
    _append_resolved_model_section(
        lines,
        label="Chat",
        explicit_provider_key="UAGENT_PROVIDER",
        resolved=(provider, "test-model"),
        model_explicit_keys=["UAGENT_DEPNAME"],
    )
    return lines


def test_local_provider_display_mentions_api_key_is_not_required(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "en")
    set_thread_lang("en")
    assert any("API key not required" in line for line in _render("ollama"))
    assert any("API key not required" in line for line in _render("llama_cpp"))
    assert any("API key not required" in line for line in _render("lmstudio"))


def test_cloud_and_api_key_provider_display_auth_requirement(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "en")
    set_thread_lang("en")
    assert any("cloud credentials" in line for line in _render("bedrock"))
    assert any("API key" in line for line in _render("openai"))


def test_unknown_provider_display_is_conservative(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_LANG", "en")
    set_thread_lang("en")
    assert any("unknown" in line for line in _render("future-provider"))

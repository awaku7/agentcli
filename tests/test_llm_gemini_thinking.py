from __future__ import annotations

from uagent.providers import llm_gemini


class _GeminiTypes:
    class ThinkingConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


def test_minimal_uses_llmcapa_low_level(monkeypatch):
    monkeypatch.setattr(
        llm_gemini, "_llmcapa_reasoning_levels", lambda model: {"low", "medium", "high"}
    )
    monkeypatch.setattr(llm_gemini, "_model_uses_thinking_budget", lambda model: False)

    cfg = llm_gemini._build_thinking_config(
        gemini_types=_GeminiTypes,
        model_name="gemini-test",
        reasoning_mode="minimal",
        user_text_for_auto="",
    )

    assert cfg.kwargs["thinking_level"] == "low"


def test_llmcapa_non_reasoning_model_disables_thinking(monkeypatch):
    monkeypatch.setattr(llm_gemini, "_llmcapa_reasoning_levels", lambda model: set())

    cfg = llm_gemini._build_thinking_config(
        gemini_types=_GeminiTypes,
        model_name="gemini-2.0-flash",
        reasoning_mode="auto",
        user_text_for_auto="short request",
    )

    assert cfg is None


def test_unknown_model_does_not_send_minimal(monkeypatch):
    monkeypatch.setattr(llm_gemini, "_llmcapa_reasoning_levels", lambda model: None)
    monkeypatch.setattr(llm_gemini, "_model_uses_thinking_budget", lambda model: False)

    cfg = llm_gemini._build_thinking_config(
        gemini_types=_GeminiTypes,
        model_name="unknown-gemini",
        reasoning_mode="minimal",
        user_text_for_auto="",
    )

    assert cfg.kwargs["thinking_level"] == "low"
    assert cfg.kwargs["thinking_level"] != "minimal"


def test_auto_reasoning_ignores_short_continuation_prompt():
    from uagent.providers.llm_gemini import _extract_latest_user_text

    messages = [
        {"role": "user", "content": "デバッグして原因を分析してください。"},
        {"role": "user", "content": "続けて"},
    ]

    assert _extract_latest_user_text(messages) == messages[0]["content"]


def test_auto_reasoning_recognizes_japanese_analysis_task():
    from uagent.providers.llm_gemini import _choose_auto_thinking_level

    assert _choose_auto_thinking_level("原因を分析して修正してください") == "low"

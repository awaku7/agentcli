from __future__ import annotations

import pytest

from uagent.runtime import legacy_provider_dispatch as dispatch


def test_gemini_dispatch_uses_provider_registry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_caller(**kwargs):
        calls.append(kwargs)
        return "gemini-result"

    monkeypatch.setitem(dispatch._LEGACY_GEMINI_ROUND_CALLERS, "gemini", fake_caller)

    result = dispatch.call_legacy_gemini_round(provider="gemini", marker=1)

    assert result == "gemini-result"
    assert calls == [{"marker": 1}]


def test_gemini_dispatch_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unsupported Gemini provider"):
        dispatch.call_legacy_gemini_round(provider="unknown")


def test_reasoning_dispatch_uses_provider_registry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_caller(**kwargs):
        calls.append(kwargs)
        return "reasoning-result"

    monkeypatch.setitem(
        dispatch._LEGACY_REASONING_ROUND_CALLERS, "deepseek", fake_caller
    )

    result = dispatch.call_legacy_reasoning_round(provider="deepseek", marker=2)

    assert result == "reasoning-result"
    assert calls == [{"marker": 2}]


def test_deepseek_responses_route_uses_openai_compatible_dispatch(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_openai(**kwargs):
        calls.append(kwargs)
        return "responses-result"

    monkeypatch.setattr(dispatch, "_call_openai_azure_round", fake_openai)
    kwargs = {
        "provider": "deepseek",
        "use_responses_api": True,
        "client": object(),
        "depname": "deepseek-model",
        "call_messages": [],
        "core": object(),
        "make_client_fn": object(),
        "call_maybe_thread_fn": object(),
        "stream_responses": False,
        "send_tools_this_round": False,
        "max_retries_429": 0,
        "retry_base": 0.0,
        "retry_cap": 0.0,
        "messages": [],
        "responses_state": {},
    }

    assert dispatch.call_legacy_deepseek_round(**kwargs) == "responses-result"
    assert calls and calls[0]["provider"] == "deepseek"


def test_mimo_chat_route_uses_deepseek_dispatch(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_deepseek(**kwargs):
        calls.append(kwargs)
        return "chat-result"

    monkeypatch.setattr(dispatch, "_call_deepseek_round", fake_deepseek)
    kwargs = {
        "provider": "mimo",
        "use_responses_api": False,
        "client": object(),
        "depname": "mimo-model",
        "call_messages": [],
        "core": object(),
        "make_client_fn": object(),
        "call_maybe_thread_fn": object(),
        "stream_responses": False,
        "send_tools_this_round": False,
        "max_retries_429": 0,
        "retry_base": 0.0,
        "retry_cap": 0.0,
        "messages": [],
        "responses_state": {},
    }

    assert dispatch.call_legacy_deepseek_round(**kwargs) == "chat-result"
    assert calls and calls[0]["provider"] == "mimo"


def test_reasoning_dispatch_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unsupported legacy reasoning provider"):
        dispatch.call_legacy_reasoning_round(provider="unknown")


__all__ = []


if __name__ == "__main__":
    raise SystemExit("pytest is required")

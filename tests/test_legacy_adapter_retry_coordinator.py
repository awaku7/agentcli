from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.legacy_claude_adapter import _call_claude_round
from uagent.runtime.legacy_gemini_adapter import _call_gemini_round


class FakeRetryCoordinator:
    def __init__(
        self, *, authorize: bool = True, rate_limit_action: str = "retry"
    ) -> None:
        self.budget = object()
        self.calls: list[dict[str, object]] = []
        self.authorizations: list[tuple[str, str]] = []
        self.authorize_result = authorize
        self.rate_limit_action = rate_limit_action

    def expose_budget(self, core: object) -> None:
        core.round_attempt_budget = self.budget

    def rate_limit_step(self, **kwargs: object) -> tuple[int, None, str]:
        self.calls.append(kwargs)
        return int(kwargs["attempt"]) + 1, None, self.rate_limit_action

    def authorize(self, reason: str, detail: str) -> bool:
        self.authorizations.append((reason, detail))
        return self.authorize_result


def test_gemini_adapter_routes_retry_through_round_coordinator() -> None:
    coordinator = FakeRetryCoordinator()
    core = SimpleNamespace(_is_web=True)
    calls = 0

    def gemini_chat(*_args: object, **_kwargs: object):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("429")
        return "answer", [], {}

    result = _call_gemini_round(
        client=object(),
        depname="gemini-model",
        call_messages=[],
        gemini_cache_name=None,
        core=core,
        make_client_fn=lambda _core: (None, object()),
        call_maybe_thread_fn=lambda fn: fn(),
        max_retries_429=2,
        retry_base=0.0,
        retry_cap=0.0,
        stream_responses=False,
        gemini_chat_fn=gemini_chat,
        retry_coordinator=coordinator,
    )

    assert result[0] is True
    assert result[2] == "answer"
    assert core.round_attempt_budget is coordinator.budget
    assert coordinator.calls[0]["provider"] == "gemini"


def test_claude_adapter_routes_retry_through_round_coordinator() -> None:
    coordinator = FakeRetryCoordinator()
    core = SimpleNamespace()
    calls = 0

    def claude_chat(*_args: object, **_kwargs: object):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("429")
        return "answer", []

    result = _call_claude_round(
        client=object(),
        depname="claude-model",
        call_messages=[],
        core=core,
        make_client_fn=lambda _core: (None, object()),
        call_maybe_thread_fn=lambda fn: fn(),
        max_retries_429=2,
        retry_base=0.0,
        retry_cap=0.0,
        claude_chat_fn=claude_chat,
        retry_coordinator=coordinator,
    )

    assert result[0] is True
    assert result[2] == "answer"
    assert core.round_attempt_budget is coordinator.budget
    assert coordinator.calls[0]["provider"] == "claude"


def test_gemini_adapter_authorizes_thinking_fallback(monkeypatch) -> None:
    coordinator = FakeRetryCoordinator(rate_limit_action="not_rate_limited")
    calls = 0
    reasoning_modes: list[str] = []
    monkeypatch.setattr("uagent.util_tools.set_reasoning_mode", reasoning_modes.append)

    def gemini_chat(*_args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Thinking level MINIMAL is not supported for this model")
        assert kwargs["force_thinking_level"] == "medium"
        return "answer", [], {}

    result = _call_gemini_round(
        client=object(),
        depname="gemini-model",
        call_messages=[],
        gemini_cache_name=None,
        core=SimpleNamespace(_is_web=True),
        make_client_fn=lambda _core: (None, object()),
        call_maybe_thread_fn=lambda fn: fn(),
        max_retries_429=0,
        retry_base=0.0,
        retry_cap=0.0,
        stream_responses=False,
        gemini_chat_fn=gemini_chat,
        retry_coordinator=coordinator,
    )

    assert result[0] is True
    assert coordinator.authorizations == [
        ("feature_fallback", "gemini thinking level unsupported")
    ]
    assert reasoning_modes == ["medium"]


def test_gemini_adapter_stops_when_thinking_fallback_budget_is_denied() -> None:
    coordinator = FakeRetryCoordinator(
        authorize=False, rate_limit_action="not_rate_limited"
    )
    calls = 0

    def gemini_chat(*_args: object, **_kwargs: object):
        nonlocal calls
        calls += 1
        raise RuntimeError("Thinking level MINIMAL is not supported for this model")

    result = _call_gemini_round(
        client=object(),
        depname="gemini-model",
        call_messages=[],
        gemini_cache_name=None,
        core=SimpleNamespace(_is_web=True),
        make_client_fn=lambda _core: (None, object()),
        call_maybe_thread_fn=lambda fn: fn(),
        max_retries_429=0,
        retry_base=0.0,
        retry_cap=0.0,
        stream_responses=False,
        gemini_chat_fn=gemini_chat,
        retry_coordinator=coordinator,
    )

    assert result[0] is False
    assert calls == 1
    assert coordinator.authorizations == [
        ("feature_fallback", "gemini thinking level unsupported")
    ]


__all__ = []

from __future__ import annotations

from uagent.runtime import legacy_round_registry


def test_registry_dispatches_registered_provider(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_handler(**kwargs):
        calls.append(kwargs)
        return ("ok", "client", None, 0, "answer")

    monkeypatch.setitem(
        legacy_round_registry._LEGACY_ROUND_HANDLERS, "claude", fake_handler
    )

    result = legacy_round_registry.run_legacy_provider_round(
        provider="claude", marker=1
    )

    assert result == ("ok", "client", None, 0, "answer")
    assert calls == [{"provider": "claude", "marker": 1}]


def test_legacy_provider_outcome_wraps_without_changing_raw_result(monkeypatch) -> None:
    raw_result = ("continue", "client", "cache", 2, "partial answer")

    def fake_handler(**kwargs):
        return raw_result

    monkeypatch.setitem(
        legacy_round_registry._LEGACY_ROUND_HANDLERS, "claude", fake_handler
    )

    outcome = legacy_round_registry.run_legacy_provider_outcome(
        provider="claude", marker=1
    )

    assert outcome is not None
    assert outcome.provider == "claude"
    assert outcome.status == "continue"
    assert outcome.assistant_text == "partial answer"
    assert outcome.raw_result == raw_result
    assert outcome.capabilities.owns_tool_execution is True
    assert outcome.capabilities.host_rendered is True
    assert outcome.summary is not None
    assert outcome.summary.status == "continue"


def test_legacy_provider_return_action_preserves_failure_summary(monkeypatch) -> None:
    raw_result = ("return", "client", "cache", 0, "provider error")

    monkeypatch.setitem(
        legacy_round_registry._LEGACY_ROUND_HANDLERS,
        "claude",
        lambda **_kwargs: raw_result,
    )

    outcome = legacy_round_registry.run_legacy_provider_outcome(provider="claude")

    assert outcome is not None
    assert outcome.status == "return"
    assert outcome.summary is not None
    assert outcome.summary.status == "failed"


def test_legacy_provider_break_action_preserves_interrupted_summary(monkeypatch) -> None:
    raw_result = ("break", "client", "cache", 0, "partial answer")

    monkeypatch.setitem(
        legacy_round_registry._LEGACY_ROUND_HANDLERS,
        "claude",
        lambda **_kwargs: raw_result,
    )

    outcome = legacy_round_registry.run_legacy_provider_outcome(provider="claude")

    assert outcome is not None
    assert outcome.status == "break"
    assert outcome.summary is not None
    assert outcome.summary.status == "interrupted"


def test_registry_returns_none_for_unregistered_provider() -> None:
    assert legacy_round_registry.run_legacy_provider_round(provider="openai") is None
    assert legacy_round_registry.run_legacy_provider_outcome(provider="openai") is None


__all__ = []

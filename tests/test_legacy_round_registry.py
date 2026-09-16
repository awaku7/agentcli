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


def test_registry_returns_none_for_unregistered_provider() -> None:
    assert legacy_round_registry.run_legacy_provider_round(provider="openai") is None


__all__ = []

from __future__ import annotations

from uagent.runtime import openai_special_dispatch


def test_special_openai_dispatch_routes_registered_provider(monkeypatch) -> None:
    calls = []

    monkeypatch.setitem(
        openai_special_dispatch._SPECIAL_OPENAI_HANDLERS,
        "pfn",
        lambda **kwargs: calls.append(kwargs) or (True,),
    )

    assert openai_special_dispatch.call_special_openai_round(
        provider="pfn", marker=1
    ) == (True,)
    assert calls == [{"marker": 1}]


def test_special_openai_dispatch_returns_none_for_normal_provider() -> None:
    assert openai_special_dispatch.call_special_openai_round(provider="openai") is None


__all__ = []

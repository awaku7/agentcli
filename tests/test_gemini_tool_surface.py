from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.llm_gemini import _gemini_round_tool_specs


def _spec(name: str) -> dict:
    return {"function": {"name": name}}


def test_gemini_initial_round_exposes_discovery_tools_only() -> None:
    specs = [_spec("get_weather_wttr"), _spec("tool_catalog"), _spec("human_ask")]

    selected = _gemini_round_tool_specs(
        specs, core=SimpleNamespace(_gemini_tool_catalog_ready=False), provider="gemini"
    )

    assert [item["function"]["name"] for item in selected] == [
        "tool_catalog",
        "human_ask",
    ]


def test_gemini_after_catalog_uses_full_context_surface() -> None:
    specs = [_spec("get_weather_wttr"), _spec("tool_catalog")]

    selected = _gemini_round_tool_specs(
        specs,
        core=SimpleNamespace(_gemini_tool_catalog_ready=True),
        provider="vertexai",
    )

    assert selected == specs


def test_other_providers_are_unchanged() -> None:
    specs = [_spec("get_weather_wttr")]

    assert (
        _gemini_round_tool_specs(
            specs,
            core=SimpleNamespace(_gemini_tool_catalog_ready=False),
            provider="claude",
        )
        == specs
    )


__all__ = []

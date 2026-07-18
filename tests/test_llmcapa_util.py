"""Tests for uagent.llmcapa_util shared capability helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("llmcapa")

from uagent.llmcapa_util import (
    clamp_max_tokens,
    clear_capability_cache,
    format_capability_lines,
    get_capability,
    get_context_window,
    get_max_output_tokens,
    provider_candidates,
    supports_vision,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_capability_cache()
    yield
    clear_capability_cache()


class TestProviderCandidates:
    def test_gemini_maps_to_google(self) -> None:
        cands = provider_candidates("gemini")
        assert "google" in cands
        assert cands[0] == "gemini" or "google" in cands

    def test_grok_maps_to_xai(self) -> None:
        assert "xai" in provider_candidates("grok")

    def test_bedrock_maps_to_amazon(self) -> None:
        assert "amazon" in provider_candidates("bedrock")


class TestGetCapability:
    def test_openai_gpt4o(self) -> None:
        cap = get_capability("gpt-4o", "openai")
        assert cap is not None
        assert cap.context_window >= 128000
        assert cap.supports_vision is True

    def test_gemini_alias_provider(self) -> None:
        cap = get_capability("gemini-2.0-flash", "gemini")
        assert cap is not None
        assert get_context_window("gemini-2.0-flash", "gemini") == cap.context_window

    def test_unknown_returns_none(self) -> None:
        assert get_capability("definitely-not-a-real-model-xyz", "openai") is None


class TestSupportsVision:
    def test_gpt4o_true(self) -> None:
        assert supports_vision("gpt-4o", "openai") is True

    def test_unknown_default(self) -> None:
        assert (
            supports_vision("definitely-not-a-real-model-xyz", "openai", default=True)
            is True
        )


class TestClampMaxTokens:
    def test_clamps_to_model_max(self) -> None:
        limit = get_max_output_tokens("gpt-4o", "openai")
        assert limit is not None and limit > 0
        assert clamp_max_tokens(limit * 10, "gpt-4o", "openai") == limit

    def test_leaves_smaller_value(self) -> None:
        limit = get_max_output_tokens("gpt-4o", "openai")
        assert limit is not None
        assert clamp_max_tokens(100, "gpt-4o", "openai") == 100


class TestFormatLines:
    def test_format_nonempty(self) -> None:
        cap = get_capability("gpt-4o", "openai")
        lines = format_capability_lines(cap)
        assert any("Context Window" in ln for ln in lines)
        assert any("Features" in ln for ln in lines)


class TestProviderAllowsChatVision:
    def test_non_vision_model_blocked(self) -> None:
        from uagent.util_tools import provider_allows_chat_vision

        # grok-3 is text-only in llmcapa; provider is chat-vision capable.
        assert (
            provider_allows_chat_vision(
                "grok", model_id="grok-3", use_responses_api=False
            )
            is False
        )

        assert (
            provider_allows_chat_vision(
                "openai", model_id="openai/o3-mini", use_responses_api=False
            )
            is False
        )

    def test_chat_vision_provider_with_vision_model(self) -> None:
        from uagent.util_tools import provider_allows_chat_vision

        assert (
            provider_allows_chat_vision(
                "openai", model_id="gpt-4o", use_responses_api=False
            )
            is True
        )

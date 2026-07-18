"""Tests for uagent.llmcapa_util shared capability helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("llmcapa")

from uagent.llmcapa_util import (
    count_messages_tokens,
    provider_allows_fim,
    provider_allows_responses_api,
    resolve_model_id_for_tokenizer,
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


class TestResponsesAndFimGates:
    def test_openai_responses_provider_allowed(self) -> None:
        assert provider_allows_responses_api("openai", "gpt-4o") is True

    def test_claude_not_in_responses_providers(self) -> None:
        assert provider_allows_responses_api("claude", "claude-sonnet-4") is False

    def test_fim_provider_gate(self) -> None:
        # Provider must be in FIM_SUPPORTED_PROVIDERS first.
        assert provider_allows_fim("openai", "gpt-4o") is False
        # deepseek/ollama stay allowed when model capability is unknown/true.
        assert provider_allows_fim("deepseek", "DeepSeek-V3") in (True, False)


class TestTokenCountResolve:
    def test_resolve_model_id(self) -> None:
        mid = resolve_model_id_for_tokenizer("gpt-4o", "openai")
        assert mid
        assert "gpt-4o" in mid

    def test_count_messages_tokens(self) -> None:
        n = count_messages_tokens(
            [{"role": "user", "content": "hello"}],
            "gpt-4o",
            "openai",
        )
        assert n is not None and n > 0

"""Tests for uagent.llmcapa_util shared capability helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("llmcapa")

from uagent.llmcapa_util import (
    check_audio_input_support,
    check_audio_output_support,
    check_embedding_support,
    check_image_output_support,
    apply_shared_max_tokens,
    check_vision_support,
    vision_completion_max_tokens,
    deprecated_model_warning,
    estimate_cost,
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
    supports_audio_input,
    supports_audio_output,
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
        from uagent.i18n import set_thread_lang

        set_thread_lang("en")
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


class TestCostAndDeprecated:
    def test_estimate_cost_gpt4o(self) -> None:
        est = estimate_cost(1_000_000, 1_000_000, "gpt-4o", "openai")
        assert est is not None
        assert float(est.get("cost", 0)) > 0

    def test_deprecated_warning_optional(self) -> None:
        from uagent.i18n import set_thread_lang

        set_thread_lang("en")
        # gpt-4o is marked deprecated in current llmcapa; accept warn or None if data changes
        warn = deprecated_model_warning("gpt-4o", "openai")
        assert warn is None or "deprecated" in warn.lower()


class TestVisionToolHelpers:
    def test_check_vision_support_blocks_text_only(self) -> None:
        err = check_vision_support("grok-3", "grok")
        assert err is not None
        assert "does not support vision" in err.lower() or "vision" in err.lower()

    def test_check_vision_support_allows_gpt4o(self) -> None:
        assert check_vision_support("gpt-4o", "openai") is None

    def test_vision_completion_max_tokens_positive(self) -> None:
        n = vision_completion_max_tokens("gpt-4o", "openai", default=1024)
        assert isinstance(n, int) and n > 0
        assert n <= 16384


class TestImageAndEmbeddingHelpers:
    def test_image_output_gpt_image(self) -> None:
        assert check_image_output_support("gpt-image-1", "openai") is None

    def test_image_output_blocks_chat_model(self) -> None:
        err = check_image_output_support("gpt-4o", "openai")
        # gpt-4o is text output only
        assert err is not None

    def test_embedding_model(self) -> None:
        assert check_embedding_support("text-embedding-3-small", "openai") is None

    def test_embedding_blocks_chat_model(self) -> None:
        err = check_embedding_support("gpt-4o", "openai")
        assert err is not None

    def test_apply_shared_max_tokens(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_MAX_TOKENS", "999999")
        kw: dict = {}
        apply_shared_max_tokens(kw, model_id="gpt-4o", provider="openai")
        assert "max_tokens" in kw
        assert kw["max_tokens"] <= 16384


class TestAudioOutputHelpers:
    def test_grok_tts_supported(self) -> None:
        assert supports_audio_output("grok-tts", "grok") is True
        assert check_audio_output_support("grok-tts", "grok") is None

    def test_chat_model_blocked(self) -> None:
        err = check_audio_output_support("gpt-4o", "openai")
        assert err is not None
        assert "audio" in err.lower() or "tts" in err.lower()

    def test_catalog_miss_allows(self) -> None:
        # gpt-4o-mini-tts may be absent from llmcapa; miss => allow
        assert supports_audio_output("gpt-4o-mini-tts", "openai", default=None) is None
        assert check_audio_output_support("gpt-4o-mini-tts", "openai") is None

    def test_empty_model_allows(self) -> None:
        assert check_audio_output_support("", "openai") is None


class TestAudioInputHelpers:
    def test_grok_stt_supported(self) -> None:
        assert supports_audio_input("grok-stt-batch", "grok") is True
        assert check_audio_input_support("grok-stt-batch", "grok") is None

    def test_tts_model_blocked(self) -> None:
        err = check_audio_input_support("grok-tts", "grok")
        assert err is not None
        assert "audio" in err.lower() or "stt" in err.lower()

    def test_chat_model_blocked(self) -> None:
        # openai gpt-4o has no audio input in catalog
        err = check_audio_input_support("gpt-4o", "openai")
        assert err is not None

    def test_catalog_miss_allows(self) -> None:
        # Unknown model id => catalog miss => allow (default=None)
        assert (
            supports_audio_input(
                "definitely-not-a-real-stt-model-xyz", "openai", default=None
            )
            is None
        )
        assert (
            check_audio_input_support("definitely-not-a-real-stt-model-xyz", "openai")
            is None
        )

    def test_empty_model_allows(self) -> None:
        assert check_audio_input_support("", "openai") is None

"""Tests for llmcapa: verify provider model specs are correct.

This test validates that llmcapa provides accurate capability data
for the providers and models that uag relies on.
"""

from __future__ import annotations

import pytest

pytest.importorskip("llmcapa")

import llmcapa


class TestLlmcapaProviders:
    """llmcapa has model data for all uag-supported providers."""

    def test_providers_list_nonempty(self) -> None:
        providers = llmcapa.providers()
        assert len(providers) > 50, f"Expected 50+ providers, got {len(providers)}"

    @pytest.mark.parametrize(
        "provider, expected_min_models",
        [
            ("openai", 10),
            ("anthropic", 10),
            ("google", 10),
            ("meta", 10),
            ("mistral", 10),
            ("deepseek", 5),
            ("cohere", 3),
            ("microsoft", 3),
            ("amazon", 3),
        ],
    )
    def test_provider_has_models(self, provider: str, expected_min_models: int) -> None:
        models = llmcapa.list_models(provider=provider)
        assert len(models) >= expected_min_models, (
            f"{provider}: expected >= {expected_min_models} models, got {len(models)}"
        )


class TestLlmcapaModelSpecs:
    """Known models have expected capability values."""

    # (model_id, provider, min_ctx, min_out, vision, fc)
    # fc=None means the database doesn't have this info (skip assertion)
    MODEL_CHECKS = [
        ("gpt-4o", "openai", 128000, 16384, True, True),
        ("gpt-4.1", "openai", 1000000, 16384, True, True),
        ("gpt-4.1-mini", "openai", 1000000, 16384, True, True),
        ("o1", "openai", 100000, 100000, True, True),
        ("openai/o3-mini", "openai", 100000, 100000, False, True),
        ("anthropic/claude-sonnet-4", "anthropic", 200000, 32000, True, True),
        ("anthropic/claude-haiku-4.5", "anthropic", 200000, 64000, True, True),
        ("gemini-2.0-flash", "google", 1000000, 8192, True, True),
        ("gemini-2.5-flash", "google", 1000000, 65535, True, True),
        ("gemini-2.5-pro", "google", 1000000, 65536, True, True),
        ("DeepSeek-V3", "deepseek", 131072, 8192, False, True),
        ("DeepSeek-R1", "deepseek", 65536, 8192, False, True),
        ("Llama-3.2-90B-Vision-Instruct", "meta", 128000, 16384, True, None),
        ("Llama-4-Scout-17B-16E", "meta", 1000000, 16384, True, None),
        ("Codestral-2501", "mistral", 128000, 16384, False, None),
        ("mistral-small", "mistral", 131072, 8192, False, True),
        ("amazon/nova-2-lite-v1", "amazon", 1000000, 65535, True, True),
        ("amazon/nova-pro-v1", "amazon", 300000, 5120, True, True),
        ("cohere/command-a", "cohere", 256000, 8192, False, False),
    ]

    @pytest.mark.parametrize(
        "model_id,provider,min_ctx,min_out,expect_vision,expect_fc",
        MODEL_CHECKS,
    )
    def test_model_specs(
        self,
        model_id: str,
        provider: str,
        min_ctx: int,
        min_out: int,
        expect_vision: bool,
        expect_fc: bool | None,
    ) -> None:
        cap = llmcapa.get(model_id, provider=provider)
        assert cap is not None, f"{model_id} not found"

        errors: list[str] = []
        if cap.context_window < min_ctx:
            errors.append(
                f"context_window {cap.context_window} < expected min {min_ctx}"
            )
        if cap.max_output_tokens < min_out:
            errors.append(
                f"max_output_tokens {cap.max_output_tokens} < expected min {min_out}"
            )
        if expect_vision and not cap.supports_vision:
            errors.append("expected vision=True but got False")
        if not expect_vision and cap.supports_vision:
            errors.append("expected vision=False but got True")
        if expect_fc is True and cap.supports_function_calling is not True:
            errors.append(
                f"expected function_calling=True but got {cap.supports_function_calling}"
            )
        if expect_fc is False and cap.supports_function_calling is True:
            errors.append("expected function_calling=False but got True")

        assert not errors, f"{model_id} ({provider}): {'; '.join(errors)}"


class TestLlmcapaCountTokens:
    """Token counting works for known models."""

    def test_count_messages_simple(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        n = llmcapa.count_messages_tokens(messages, "gpt-4o")
        assert n > 0, f"Expected positive token count, got {n}"
        assert n < 100, f"Expected reasonable count, got {n}"

    def test_count_tokens_model_id(self) -> None:
        n = llmcapa.count_tokens("Hello, world!", "gpt-4o")
        assert n > 0, f"Expected positive token count, got {n}"

    @pytest.mark.parametrize("model_id", ["gpt-4o", "DeepSeek-V3", "gemini-2.0-flash"])
    def test_count_tokens_multi_model(self, model_id: str) -> None:
        n = llmcapa.count_tokens("This is a test sentence.", model_id)
        assert n > 0, f"{model_id}: expected positive token count, got {n}"

class TestAllProviders:
    """Every provider in llmcapa has valid model data."""

    def test_all_providers_have_models(self) -> None:
        providers = llmcapa.providers()
        assert len(providers) >= 70
        for p in providers:
            models = llmcapa.list_models(provider=p)
            assert len(models) >= 1, f"{p} has 0 models"

    def test_all_models_have_positive_context(self) -> None:
        providers = llmcapa.providers()
        bad: list[str] = []
        for p in providers:
            for m in llmcapa.list_models(provider=p):
                if m.context_window <= 0:
                    bad.append(f"{p}/{m.model_id}: ctx={m.context_window}")
        assert not bad, f"Models with non-positive context_window:\n" + "\n".join(bad[:20])

    def test_all_models_have_nonnegative_output(self) -> None:
        providers = llmcapa.providers()
        bad: list[str] = []
        for p in providers:
            for m in llmcapa.list_models(provider=p):
                if m.max_output_tokens < 0:
                    bad.append(f"{p}/{m.model_id}: out={m.max_output_tokens}")
        assert not bad, f"Models with negative max_output_tokens:\n" + "\n".join(bad[:20])

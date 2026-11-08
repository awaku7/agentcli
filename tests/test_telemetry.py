from __future__ import annotations

from uagent.runtime.telemetry import (
    estimate_context_components,
    provider_cache_usage,
    reconcile_usage,
)


def test_reconcile_usage_returns_known_token_deltas_only() -> None:
    assert reconcile_usage(
        {"input_tokens": 10, "output_tokens": 2},
        {"input_tokens": 15, "output_tokens": 5, "total_tokens": 20},
    ) == {
        "input_tokens_delta": 5,
        "output_tokens_delta": 3,
        "total_tokens_delta": 20,
    }


def test_reconcile_usage_omits_unavailable_provider_fields() -> None:
    assert reconcile_usage({}, {"input_tokens": "unknown"}) == {}


def test_cache_read_usage_is_a_subset_not_a_second_input_total() -> None:
    assert provider_cache_usage(
        {"input_tokens_details": {"cached_tokens": 27}}, responses=True
    ) == {"cache_read_input_tokens": 27}
    assert provider_cache_usage(
        {"prompt_tokens_details": {"cached_tokens": 9}}, responses=False
    ) == {"cache_read_input_tokens": 9}
    assert (
        provider_cache_usage(
            {"input_tokens_details": {"cached_tokens": "unknown"}}, responses=True
        )
        == {}
    )
    assert reconcile_usage(
        None, {"input_tokens": 50, "cache_read_input_tokens": 27}
    ) == {
        "input_tokens_delta": 50,
        "cache_read_input_tokens_delta": 27,
    }


def test_context_breakdown_does_not_expose_message_bodies() -> None:
    result = estimate_context_components(
        {
            "messages": [
                {"role": "system", "content": "PRIVATE_SYSTEM"},
                {"role": "user", "content": "PRIVATE_USER"},
                {"role": "assistant", "content": "old answer"},
            ],
            "tools": [{"type": "function", "name": "read_file"}],
        },
    )
    assert all(type(v) is int and v > 0 for v in result.values())
    assert set(result) == {
        "uag.tokens.context.instructions",
        "uag.tokens.context.messages",
        "uag.tokens.context.tools",
    }
    assert "PRIVATE_USER" not in str(result)
    assert estimate_context_components({}, provider="openai") == {}

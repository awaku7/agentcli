from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.telemetry import (
    anthropic_usage_to_dict,
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


def test_anthropic_usage_includes_cache_read_and_write_in_total_input() -> None:
    usage = SimpleNamespace(
        input_tokens=12,
        output_tokens=7,
        cache_read_input_tokens=80,
        cache_creation_input_tokens=25,
    )
    assert anthropic_usage_to_dict(usage) == {
        "input_tokens": 117,
        "output_tokens": 7,
        "total_tokens": 124,
        "cache_read_input_tokens": 80,
        "cache_write_input_tokens": 25,
    }


def test_anthropic_usage_preserves_explicit_zero_and_unreported_fields() -> None:
    assert anthropic_usage_to_dict({"input_tokens": 14, "output_tokens": 2}) == {
        "input_tokens": 14,
        "output_tokens": 2,
        "total_tokens": 16,
    }
    assert anthropic_usage_to_dict(
        {"input_tokens": 6, "cache_read_input_tokens": 0}
    ) == {"input_tokens": 6, "cache_read_input_tokens": 0}
    assert anthropic_usage_to_dict(
        {
            "input_tokens": 14,
            "output_tokens": 2,
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": None,
        }
    ) == {"input_tokens": 14, "output_tokens": 2, "total_tokens": 16}
    assert anthropic_usage_to_dict(None) == {}


def test_anthropic_usage_rejects_invalid_counts_without_fabricating_totals() -> None:
    assert (
        anthropic_usage_to_dict(
            {
                "input_tokens": 10,
                "output_tokens": True,
                "cache_read_input_tokens": -1,
                "cache_creation_input_tokens": "unknown",
            }
        )
        == {}
    )
    assert anthropic_usage_to_dict(
        {
            "input_tokens": 10,
            "output_tokens": 2,
            "cache_read_input_tokens": 10**12 + 1,
        }
    ) == {"output_tokens": 2}
    assert anthropic_usage_to_dict(
        {
            "input_tokens": 10,
            "output_tokens": 2,
            "cache_creation_input_tokens": False,
        }
    ) == {"output_tokens": 2}
    assert anthropic_usage_to_dict(
        {
            "input_tokens": 10**12,
            "cache_read_input_tokens": 1,
            "output_tokens": 2,
        }
    ) == {"output_tokens": 2}
    assert anthropic_usage_to_dict({"output_tokens": 9}) == {"output_tokens": 9}


def test_normalized_provider_cache_usage_includes_cache_write() -> None:
    usage = anthropic_usage_to_dict(
        {
            "input_tokens": 15,
            "cache_read_input_tokens": 20,
            "cache_creation_input_tokens": 30,
            "output_tokens": 4,
        }
    )
    assert provider_cache_usage(usage, responses=True) == {
        "cache_read_input_tokens": 20,
        "cache_write_input_tokens": 30,
    }
    assert reconcile_usage(None, usage) == {
        "input_tokens_delta": 65,
        "output_tokens_delta": 4,
        "total_tokens_delta": 69,
        "cache_read_input_tokens_delta": 20,
        "cache_write_input_tokens_delta": 30,
    }

from __future__ import annotations

from uagent.runtime.telemetry import reconcile_usage


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

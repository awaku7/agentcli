"""Sakana Fugu Responses measured usage with separate orchestration tokens."""

from __future__ import annotations

from typing import Any, Mapping


def _field(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, Mapping) else getattr(value, key, None)


def _tokens(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 10**12


def sakana_responses_usage_to_dict(usage: Any) -> dict[str, int]:
    """Reconcile model and orchestration tokens without counting them twice."""
    if usage is None:
        return {}

    prompt = _field(usage, "input_tokens")
    completion = _field(usage, "output_tokens")
    total = _field(usage, "total_tokens")
    input_details = _field(usage, "input_tokens_details")
    output_details = _field(usage, "output_tokens_details")
    cache = _field(input_details, "cached_tokens")
    orchestration_input = _field(input_details, "orchestration_input_tokens")
    orchestration_output = _field(output_details, "orchestration_output_tokens")
    orchestration_cache = _field(input_details, "orchestration_input_cached_tokens")

    result: dict[str, int] = {}
    if _tokens(prompt):
        result["input_tokens"] = prompt
        if _tokens(cache) and cache <= prompt:
            result["cache_read_input_tokens"] = cache
    if _tokens(completion):
        result["output_tokens"] = completion
    if _tokens(total):
        result["total_tokens"] = total

    # Fugu Ultra/Cyber report orchestration outside the input/output fields.
    # Only aggregate when every component is trustworthy and reconciles
    # exactly with the provider's total. Otherwise preserve raw reported
    # counts rather than presenting an invented adjusted measurement.
    if orchestration_input is None and orchestration_output is None:
        return result
    if not (
        _tokens(prompt)
        and _tokens(completion)
        and _tokens(total)
        and _tokens(orchestration_input)
        and _tokens(orchestration_output)
    ):
        return result

    aggregate_input = prompt + orchestration_input
    aggregate_output = completion + orchestration_output
    if aggregate_input > 10**12 or aggregate_output > 10**12:
        return result
    if aggregate_input + aggregate_output != total:
        return result
    result["input_tokens"] = aggregate_input
    result["output_tokens"] = aggregate_output
    if _tokens(orchestration_cache) and orchestration_cache <= orchestration_input:
        original_cache = result.get("cache_read_input_tokens", 0)
        if original_cache + orchestration_cache <= aggregate_input:
            result["cache_read_input_tokens"] = original_cache + orchestration_cache
    return result

"""Moonshot/Kimi Chat Completions request-scoped token usage."""

from __future__ import annotations

from typing import Any, Mapping


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def _valid_tokens(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 10**12


def moonshot_chat_usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize measured totals and cache/reasoning subsets without adding them twice."""
    if usage is None:
        return {}

    prompt = _field(usage, "prompt_tokens")
    completion = _field(usage, "completion_tokens")
    cached = _field(usage, "cached_tokens")
    if cached is None:
        cached = _field(_field(usage, "prompt_tokens_details"), "cached_tokens")
    reasoning = _field(_field(usage, "completion_tokens_details"), "reasoning_tokens")

    result: dict[str, int] = {}
    if _valid_tokens(prompt):
        result["input_tokens"] = prompt
        if _valid_tokens(cached) and cached <= prompt:
            result["cache_read_input_tokens"] = cached
    if _valid_tokens(completion):
        result["output_tokens"] = completion
        if _valid_tokens(reasoning) and reasoning <= completion:
            result["reasoning_output_tokens"] = reasoning
    if "input_tokens" in result and "output_tokens" in result:
        total = result["input_tokens"] + result["output_tokens"]
        if _valid_tokens(total):
            result["total_tokens"] = total
    return result

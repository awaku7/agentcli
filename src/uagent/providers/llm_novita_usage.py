"""Novita AI Chat Completions request-scoped usage accounting."""

from __future__ import annotations

from typing import Any, Mapping


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def _valid_token_count(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 10**12


def novita_chat_usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize measured Novita usage; never add token subsets twice."""
    if usage is None:
        return {}

    prompt = _field(usage, "prompt_tokens")
    completion = _field(usage, "completion_tokens")
    prompt_details = _field(usage, "prompt_tokens_details")
    completion_details = _field(usage, "completion_tokens_details")
    cached = _field(prompt_details, "cached_tokens")
    cache_written = _field(prompt_details, "cache_write_tokens")
    reasoning = _field(completion_details, "reasoning_tokens")

    result: dict[str, int] = {}
    if _valid_token_count(prompt):
        result["input_tokens"] = prompt
        if _valid_token_count(cached) and cached <= prompt:
            result["cache_read_input_tokens"] = cached
        if _valid_token_count(cache_written) and cache_written <= prompt:
            result["cache_write_input_tokens"] = cache_written
    if _valid_token_count(completion):
        result["output_tokens"] = completion
        if _valid_token_count(reasoning) and reasoning <= completion:
            result["reasoning_output_tokens"] = reasoning
    if "input_tokens" in result and "output_tokens" in result:
        total = result["input_tokens"] + result["output_tokens"]
        if total <= 10**12:
            result["total_tokens"] = total
    return result


def request_novita_stream_usage(payload: dict[str, Any]) -> None:
    """Request the terminal usage chunk without discarding caller options."""
    options = dict(payload.get("stream_options") or {})
    options.setdefault("include_usage", True)
    payload["stream_options"] = options


def publish_novita_usage(core: Any, measured: dict[str, int]) -> None:
    """Publish only after the owning request has completed successfully."""
    if core is None or not measured:
        return
    try:
        core._last_responses_usage = measured
    except (AttributeError, TypeError):
        pass

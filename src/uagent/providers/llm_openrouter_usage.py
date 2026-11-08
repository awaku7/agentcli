"""OpenRouter request-scoped measured token accounting."""

from __future__ import annotations

from typing import Any, Mapping


def _field(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, Mapping) else getattr(obj, name, None)


def _tokens(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 10**12


def openrouter_usage_to_dict(usage: Any, *, responses: bool) -> dict[str, int]:
    """Normalize only reported counts; subsets never increase input/output."""
    if usage is None:
        return {}
    input_count = _field(usage, "input_tokens" if responses else "prompt_tokens")
    output_count = _field(usage, "output_tokens" if responses else "completion_tokens")
    input_details = _field(
        usage, "input_tokens_details" if responses else "prompt_tokens_details"
    )
    output_details = _field(
        usage, "output_tokens_details" if responses else "completion_tokens_details"
    )
    result: dict[str, int] = {}
    if _tokens(input_count):
        result["input_tokens"] = input_count
        cached = _field(input_details, "cached_tokens")
        written = _field(input_details, "cache_write_tokens")
        if _tokens(cached) and cached <= input_count:
            result["cache_read_input_tokens"] = cached
        if _tokens(written) and written <= input_count:
            result["cache_write_input_tokens"] = written
    if _tokens(output_count):
        result["output_tokens"] = output_count
        reasoning = _field(output_details, "reasoning_tokens")
        if _tokens(reasoning) and reasoning <= output_count:
            result["reasoning_output_tokens"] = reasoning
    if "input_tokens" in result and "output_tokens" in result:
        total = result["input_tokens"] + result["output_tokens"]
        if _tokens(total):
            result["total_tokens"] = total
    return result


def request_openrouter_stream_usage(payload: dict[str, Any]) -> None:
    """Enable final usage chunks while preserving explicit caller options."""
    options = dict(payload.get("stream_options") or {})
    options.setdefault("include_usage", True)
    payload["stream_options"] = options

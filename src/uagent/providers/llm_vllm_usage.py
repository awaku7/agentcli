"""vLLM-specific OpenAI-compatible usage normalization and request options.

This module deliberately does not duplicate the shared Chat/Responses runtime.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def request_vllm_chat_stream_usage(payload: dict[str, Any]) -> None:
    """Enable final usage without overriding an explicit stream option."""
    options = dict(payload.get("stream_options") or {})
    options.setdefault("include_usage", True)
    payload["stream_options"] = options


def vllm_usage_to_dict(usage: Any, *, responses: bool) -> dict[str, int]:
    """Normalize vLLM Chat/Responses usage, preserving measured subsets only.

    vLLM reports prompt-cache reads/writes within input token totals and
    reasoning tokens within output token totals. They are never added twice.
    Cache and reasoning details vary by server version and startup flags.
    """
    if usage is None:
        return {}

    def valid(value: Any) -> bool:
        return type(value) is int and 0 <= value <= 10**12

    input_key = "input_tokens" if responses else "prompt_tokens"
    output_key = "output_tokens" if responses else "completion_tokens"
    input_tokens = _field(usage, input_key)
    output_tokens = _field(usage, output_key)
    result: dict[str, int] = {}

    if valid(input_tokens):
        result["input_tokens"] = input_tokens
        input_details = _field(
            usage, "input_tokens_details" if responses else "prompt_tokens_details"
        )
        cached = _field(input_details, "cached_tokens")
        written = _field(
            input_details, "cache_write_tokens" if responses else "created_cache_tokens"
        )
        if valid(cached) and cached <= input_tokens:
            result["cache_read_input_tokens"] = cached
        if valid(written) and written <= input_tokens:
            result["cache_write_input_tokens"] = written

    if valid(output_tokens):
        result["output_tokens"] = output_tokens
        output_details = _field(
            usage, "output_tokens_details" if responses else "completion_tokens_details"
        )
        reasoning = _field(output_details, "reasoning_tokens")
        if valid(reasoning) and reasoning <= output_tokens:
            result["reasoning_output_tokens"] = reasoning

    if "input_tokens" in result and "output_tokens" in result:
        total = result["input_tokens"] + result["output_tokens"]
        if total <= 10**12:
            result["total_tokens"] = total
    return result



def capture_vllm_responses_usage(
    stream: Any, *, provider: str, sink: list[dict[str, int]]
) -> Any:
    """Capture vLLM terminal usage without changing other providers' streams."""
    if provider != "vllm":
        return stream

    def _events() -> Iterator[Any]:
        source = (
            stream.iter_events()
            if callable(getattr(stream, "iter_events", None))
            else stream
        )
        for event in source:
            if getattr(event, "type", None) == "response.completed":
                response = getattr(event, "response", None)
                measured = vllm_usage_to_dict(
                    _field(response, "usage"), responses=True
                )
                if measured:
                    sink.append(measured)
            yield event

    return _events()


def publish_vllm_legacy_usage(core: Any, usage: Any, *, responses: bool) -> None:
    """Publish a fresh measured snapshot only after a successful legacy round."""
    if core is None:
        return
    measured = vllm_usage_to_dict(usage, responses=responses)
    if not measured:
        return
    try:
        core._last_responses_usage = measured
    except (AttributeError, TypeError):
        pass

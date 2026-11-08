"""Small helpers for reconciling optional provider usage telemetry."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .context_tokens import estimate_tokens

_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_read_input_tokens",
    "cache_write_input_tokens",
)


def reconcile_usage(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> dict[str, int]:
    """Return non-negative token deltas when provider usage is available.

    Providers may omit usage on streaming or retry responses. Missing values
    are therefore omitted rather than treated as zero, so telemetry never
    claims a precise cost from incomplete data.
    """

    previous = before if isinstance(before, Mapping) else {}
    current = after if isinstance(after, Mapping) else {}
    result: dict[str, int] = {}
    for field in _TOKEN_FIELDS:
        raw_after = current.get(field)
        if not isinstance(raw_after, (int, float)) or isinstance(raw_after, bool):
            continue
        raw_before = previous.get(field)
        before_value = (
            int(raw_before)
            if isinstance(raw_before, (int, float)) and not isinstance(raw_before, bool)
            else 0
        )
        result[f"{field}_delta"] = max(0, int(raw_after) - before_value)
    return result


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def provider_cache_usage(usage: Any, *, responses: bool) -> dict[str, int]:
    """Read provider-reported cache subset counts (never estimate them)."""
    result: dict[str, int] = {}
    for key in ("cache_read_input_tokens", "cache_write_input_tokens"):
        value = _field(usage, key)
        if type(value) is int and 0 <= value <= 10**12:
            result[key] = value
    details_key = "input_tokens_details" if responses else "prompt_tokens_details"
    details = _field(usage, details_key)
    cached = _field(details, "cached_tokens")
    if (
        "cache_read_input_tokens" not in result
        and type(cached) is int
        and 0 <= cached <= 10**12
    ):
        result["cache_read_input_tokens"] = cached
    return result


def anthropic_usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize Claude response usage to per-request totals, including cache.

    Anthropic reports uncached input separately from cache reads and writes.
    Standard GenAI input usage must contain all three portions. Missing cache
    fields remain unreported (not forced to zero in the telemetry output).
    """
    if usage is None:
        return {}
    fields: dict[str, int] = {}
    invalid_input = False
    for name in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        value = _field(usage, name)
        if value is None:
            continue
        if type(value) is int and 0 <= value <= 10**12:
            fields[name] = value
        elif name != "output_tokens":
            # An explicitly malformed component cannot be silently counted
            # as zero in a provider-reported input total.
            invalid_input = True
    result: dict[str, int] = {}
    output = fields.get("output_tokens")
    if output is not None:
        result["output_tokens"] = output
    uncached = fields.get("input_tokens")
    if uncached is not None and not invalid_input:
        total = (
            uncached
            + fields.get("cache_read_input_tokens", 0)
            + fields.get("cache_creation_input_tokens", 0)
        )
        if total <= 10**12:
            result["input_tokens"] = total
            if output is not None and total + output <= 10**12:
                result["total_tokens"] = total + output
    if "input_tokens" in result:
        for source, target in (
            ("cache_read_input_tokens", "cache_read_input_tokens"),
            ("cache_creation_input_tokens", "cache_write_input_tokens"),
        ):
            if source in fields:
                result[target] = fields[source]
    return result


def gemini_usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize Gemini/Vertex per-response metadata without double counting.

    Google counts cached content inside prompt_token_count, and reports
    tool_use_prompt_token_count as an additional input portion. Thinking
    tokens are output, not a second request or a separate billed request.
    """
    if usage is None:
        return {}
    fields: dict[str, int] = {}
    invalid_input = False
    invalid_output = False
    for key in (
        "prompt_token_count",
        "tool_use_prompt_token_count",
        "candidates_token_count",
        "thoughts_token_count",
        "cached_content_token_count",
    ):
        value = _field(usage, key)
        if value is None:
            continue
        if type(value) is int and 0 <= value <= 10**12:
            fields[key] = value
        elif key in ("candidates_token_count", "thoughts_token_count"):
            invalid_output = True
        else:
            invalid_input = True

    result: dict[str, int] = {}
    prompt = fields.get("prompt_token_count")
    cache = fields.get("cached_content_token_count")
    if prompt is not None and not invalid_input:
        count = prompt + fields.get("tool_use_prompt_token_count", 0)
        if count <= 10**12 and (cache is None or cache <= prompt):
            result["input_tokens"] = count
            if cache is not None:
                result["cache_read_input_tokens"] = cache

    candidate = fields.get("candidates_token_count")
    thoughts = fields.get("thoughts_token_count")
    if candidate is not None and not invalid_output:
        count = candidate + (thoughts or 0)
        if count <= 10**12:
            result["output_tokens"] = count
            if thoughts is not None:
                result["reasoning_output_tokens"] = thoughts

    if "input_tokens" in result and "output_tokens" in result:
        total = result["input_tokens"] + result["output_tokens"]
        if total <= 10**12:
            result["total_tokens"] = total
    return result


def deepseek_chat_usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize DeepSeek Chat Completions usage without double counting.

    Cache hits are already included in prompt_tokens. Reasoning tokens are
    already included in completion_tokens, unlike native xAI gRPC usage.
    """
    if usage is None:
        return {}

    def valid(value: Any) -> bool:
        return type(value) is int and 0 <= value <= 10**12

    prompt = _field(usage, "prompt_tokens")
    completion = _field(usage, "completion_tokens")
    cache_hit = _field(usage, "prompt_cache_hit_tokens")
    cache_miss = _field(usage, "prompt_cache_miss_tokens")
    details_cache = _field(_field(usage, "prompt_tokens_details"), "cached_tokens")
    reasoning = _field(_field(usage, "completion_tokens_details"), "reasoning_tokens")
    cached = cache_hit if cache_hit is not None else details_cache

    result: dict[str, int] = {}
    input_valid = (
        valid(prompt)
        and (cached is None or (valid(cached) and cached <= prompt))
        and (cache_miss is None or (valid(cache_miss) and cache_miss <= prompt))
        and (cache_hit is None or details_cache is None or cache_hit == details_cache)
        and (cached is None or cache_miss is None or cached + cache_miss == prompt)
    )
    if input_valid:
        result["input_tokens"] = prompt
        if cached is not None:
            result["cache_read_input_tokens"] = cached

    if valid(completion) and (
        reasoning is None or (valid(reasoning) and reasoning <= completion)
    ):
        result["output_tokens"] = completion
        if reasoning is not None:
            result["reasoning_output_tokens"] = reasoning

    if "input_tokens" in result and "output_tokens" in result:
        total = result["input_tokens"] + result["output_tokens"]
        if total <= 10**12:
            result["total_tokens"] = total
    return result

def xai_usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize native xAI gRPC usage (distinct completion and reasoning).

    Native SDK completion_tokens excludes reasoning_tokens, unlike OpenAI
    compatible REST. Cached prompt text is already part of prompt_tokens.
    """
    if usage is None:
        return {}
    result: dict[str, int] = {}
    prompt = _field(usage, "prompt_tokens")
    completion = _field(usage, "completion_tokens")
    reasoning = _field(usage, "reasoning_tokens")
    cached = _field(usage, "cached_prompt_text_tokens")

    def valid(value: Any) -> bool:
        return type(value) is int and 0 <= value <= 10**12

    if valid(prompt) and (cached is None or (valid(cached) and cached <= prompt)):
        result["input_tokens"] = prompt
        if cached is not None:
            result["cache_read_input_tokens"] = cached

    if valid(completion) and (reasoning is None or valid(reasoning)):
        total_output = completion + (reasoning or 0)
        if total_output <= 10**12:
            result["output_tokens"] = total_output
            if reasoning is not None:
                result["reasoning_output_tokens"] = reasoning

    if "input_tokens" in result and "output_tokens" in result:
        total = result["input_tokens"] + result["output_tokens"]
        if total <= 10**12:
            result["total_tokens"] = total
    return result


def estimate_context_components(
    request: Any, *, provider: str = "", model: str = ""
) -> dict[str, int]:
    """Metadata-only approximations of disjoint request components.

    Message counts include history and tool-result messages; these values are
    not provider-reported tokens and must never be added to measured usage.
    """
    payload = request if isinstance(request, Mapping) else {"messages": request}
    messages = payload.get("messages", payload.get("input"))
    instructions: list[Any] = []
    conversation: list[Any] = []
    direct = payload.get("instructions")
    if direct:
        instructions.append(direct)
    if isinstance(messages, (list, tuple)):
        for message in messages:
            if isinstance(message, Mapping) and message.get("role") in (
                "system",
                "developer",
            ):
                instructions.append(message)
            else:
                conversation.append(message)
    elif messages:
        conversation.append(messages)
    parts = {
        "instructions": instructions,
        "messages": conversation,
        "tools": payload.get("tools") or (),
    }
    estimates = {}
    for name, value in parts.items():
        if not value:
            continue
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        count = estimate_tokens(serialized, provider=provider, model=model)
        if 0 <= count <= 10**12:
            estimates["uag.tokens.context." + name] = count
    return estimates


__all__ = [
    "reconcile_usage",
    "provider_cache_usage",
    "anthropic_usage_to_dict",
    "gemini_usage_to_dict",
    "deepseek_chat_usage_to_dict",
    "xai_usage_to_dict",
    "estimate_context_components",
]

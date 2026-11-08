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
    details_key = "input_tokens_details" if responses else "prompt_tokens_details"
    details = _field(usage, details_key)
    cached = _field(details, "cached_tokens")
    if type(cached) is int and 0 <= cached <= 10**12:
        return {"cache_read_input_tokens": cached}
    return {}


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
    "estimate_context_components",
]

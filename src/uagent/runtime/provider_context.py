"""Provider-boundary projection for ContextManager output."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from typing import Any

_INTERNAL_KEYS = {
    "result_record",
    "persistent_history",
    "llm_context",
    "response_id",
    "reasoning_content",
    "_responses_output_items",
}


def apply_recovery_projection(
    messages: Sequence[Mapping[str, Any]],
    recovery_hint: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Apply only the message omissions explicitly selected by recovery.

    Recovery planning is owned by the context runtime. This helper merely
    applies that already-made decision to a provider projection and leaves the
    immutable context plan and persistent history untouched.
    """
    hint = recovery_hint or {}
    raw_indexes = hint.get("omitted_message_indexes", ())
    try:
        omitted_indexes = {int(index) for index in raw_indexes}
    except (TypeError, ValueError):
        omitted_indexes = set()
    return [
        copy.deepcopy(dict(message))
        for index, message in enumerate(messages)
        if index not in omitted_indexes and isinstance(message, Mapping)
    ]


def project_messages_for_provider(
    messages: list[dict[str, Any]], *, provider: str, model: str = ""
) -> list[dict[str, Any]]:
    """Return a provider-safe copy without changing runtime history.

    Context classification and persistence happen before this boundary.  The
    adapter only normalizes the final message shape required by provider SDKs.
    """
    del model  # Reserved for model-specific adapters.
    provider_name = str(provider or "").strip().lower()
    projected: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        item = copy.deepcopy(message)
        for key in list(item):
            if key in _INTERNAL_KEYS or str(key).startswith("_uagent_"):
                item.pop(key, None)
        if item.get("role") == "tool" and not isinstance(item.get("content"), str):
            item["content"] = json.dumps(item.get("content"), ensure_ascii=False)
        if provider_name in {"gemini", "vertexai"} and item.get("content") is None:
            item["content"] = ""
        projected.append(item)
    return projected


__all__ = ["apply_recovery_projection", "project_messages_for_provider"]

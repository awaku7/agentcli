"""Provider-boundary projection for ContextManager output."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from typing import Any

from ..providers.gemini_api_mode import gemini_api_mode
from .tool_discovery import provider_messages_api_enabled

_INTERNAL_KEYS = {
    "result_record",
    "persistent_history",
    "llm_context",
    "response_id",
    "reasoning_content",
    "reasoning",
    "_responses_output_items",
    "_gemini_content",
    "_anthropic_content_blocks",
    "actor_id",
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
    messages: list[dict[str, Any]],
    *,
    provider: str,
    model: str = "",
    preserve_responses_output_items: bool = False,
) -> list[dict[str, Any]]:
    """Return a provider-safe copy without changing runtime history.

    Context classification and persistence happen before this boundary.  The
    adapter only normalizes the final message shape required by provider SDKs.
    """
    provider_name = str(provider or "").strip().lower()
    projected: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        item = copy.deepcopy(message)
        for key in list(item):
            keep_gemini_interaction_history = (
                key == "_gemini_content"
                and provider_name in {"gemini", "vertexai"}
                and gemini_api_mode(model, provider_name) == "interactions"
            )
            keep_anthropic_messages_history = key == "_anthropic_content_blocks" and (
                provider_name == "claude"
                or (
                    provider_name in {"openrouter", "deepseek"}
                    and provider_messages_api_enabled(provider_name)
                )
            )
            keep_native_responses_output_items = (
                key == "_responses_output_items"
                and provider_name in {"openrouter", "deepseek"}
                and preserve_responses_output_items
            )
            # Sarashina requires its opaque reasoning token to be replayed in
            # the next assistant message. Keep the internal alias until its
            # provider sanitizer maps it to the documented ``reasoning`` key.
            if (
                key in _INTERNAL_KEYS
                and not keep_gemini_interaction_history
                and not keep_anthropic_messages_history
                and not keep_native_responses_output_items
                and not (
                    provider_name == "sarashina"
                    and key in {"reasoning", "reasoning_content"}
                )
            ) or str(key).startswith("_uagent_"):
                item.pop(key, None)
        if item.get("role") == "tool" and not isinstance(item.get("content"), str):
            item["content"] = json.dumps(item.get("content"), ensure_ascii=False)
        if provider_name in {"gemini", "vertexai"} and item.get("content") is None:
            item["content"] = ""
        projected.append(item)
    return projected


__all__ = ["apply_recovery_projection", "project_messages_for_provider"]

"""Provider-boundary projection for ContextManager output."""

from __future__ import annotations

import copy
import json
from typing import Any

_INTERNAL_KEYS = {"result_record", "persistent_history", "llm_context"}


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


__all__ = ["project_messages_for_provider"]

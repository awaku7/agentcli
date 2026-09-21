"""Keep derived memory context out of durable conversation history."""

from __future__ import annotations

import json
from typing import Any, Sequence

_EXPLICIT_DERIVED_PREFIXES = ("[USER PROFILE]", "[MEMORY EVIDENCE]")
_DURABLE_RUNTIME_PREFIXES = ("[CWD] ", "[SKILL] ", "[HOOK] ")
_CWD_PREFIX = "[CWD] "


def registered_memory_system_contents(core: Any) -> set[str]:
    """Return exact runtime memory/profile blocks registered on ``core``."""
    contents: set[str] = set()
    registry = getattr(core, "_uagent_memory_system_contents", {}) or {}
    if isinstance(registry, dict):
        for values in registry.values():
            if isinstance(values, (set, list, tuple)):
                contents.update(str(value) for value in values if str(value))
    forgotten = getattr(core, "_uagent_forgotten_memory_system_contents", set()) or set()
    if isinstance(forgotten, (set, list, tuple)):
        contents.update(str(value) for value in forgotten if str(value))
    return contents


def is_runtime_memory_system_message(message: Any, *, core: Any | None = None) -> bool:
    """Return True for a derived memory/profile system message."""
    if not isinstance(message, dict) or message.get("role") != "system":
        return False
    content = str(message.get("content") or "")
    if content.startswith(_EXPLICIT_DERIVED_PREFIXES):
        return True
    return core is not None and content in registered_memory_system_contents(core)


def _is_startup_cwd_message(message: Any) -> bool:
    if not isinstance(message, dict) or message.get("role") != "system":
        return False
    content = message.get("content")
    if not isinstance(content, str) or not content.startswith(_CWD_PREFIX):
        return False
    try:
        payload = json.loads(content[len(_CWD_PREFIX) :].strip())
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("event") == "startup"


def strip_derived_memory_context(
    messages: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove derived memory context from a durable/restored message sequence.

    New profile/evidence projections have explicit reserved prefixes. Older
    Personal/Shared Memory blocks did not have a stable marker, but startup
    ordering is stable: ``build_initial_messages`` inserts the startup CWD
    marker at the end of the durable leading system block and memory/profile
    blocks are appended afterwards. Therefore system messages between that
    startup marker and the first conversational message are legacy derived
    context, except for explicitly durable runtime markers.
    """
    items = [message for message in messages if isinstance(message, dict)]
    first_conversation = next(
        (index for index, message in enumerate(items) if message.get("role") != "system"),
        len(items),
    )
    startup_cwd_index: int | None = None
    for index, message in enumerate(items[:first_conversation]):
        if _is_startup_cwd_message(message):
            startup_cwd_index = index

    filtered: list[dict[str, Any]] = []
    for index, message in enumerate(items):
        if is_runtime_memory_system_message(message):
            continue
        if (
            startup_cwd_index is not None
            and startup_cwd_index < index < first_conversation
            and message.get("role") == "system"
        ):
            content = str(message.get("content") or "")
            if not content.startswith(_DURABLE_RUNTIME_PREFIXES):
                continue
        filtered.append(message)
    return filtered


__all__ = [
    "is_runtime_memory_system_message",
    "registered_memory_system_contents",
    "strip_derived_memory_context",
]

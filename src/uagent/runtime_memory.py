from __future__ import annotations

from typing import Any, Callable


def append_long_memory_system_messages(
    *,
    core: Any,
    messages: list[dict[str, Any]],
    build_long_memory_system_message_fn: Callable[[Any], dict[str, Any]],
    personal_long_memory_mod: Any,
    shared_memory_mod: Any,
) -> dict[str, bool]:
    """Append personal/shared long-term memory system messages if available."""
    flags: dict[str, bool] = {"shared_enabled": False}

    try:
        personal_records = personal_long_memory_mod.load_long_memory_records()
        personal_msg = build_long_memory_system_message_fn(personal_records)
        if personal_msg:
            messages.append(personal_msg)
            core.log_message(personal_msg)
    except Exception:
        pass

    try:
        shared_enabled = bool(shared_memory_mod.is_enabled())
    except Exception:
        shared_enabled = False

    flags["shared_enabled"] = shared_enabled
    if not shared_enabled:
        return flags

    try:
        shared_records = shared_memory_mod.load_shared_memory_records()
        shared_msg = build_long_memory_system_message_fn(shared_records)
        if shared_msg:
            messages.append(shared_msg)
            core.log_message(shared_msg)
    except Exception:
        pass

    return flags


__all__ = ["append_long_memory_system_messages"]

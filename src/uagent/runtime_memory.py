from __future__ import annotations

from typing import Any, Callable

PROFILE_MAX_ITEMS = 5
PROFILE_MAX_TEXT_CHARS = 80


def _clip(text: Any) -> str:
    return " ".join(str(text).split()).strip()[:PROFILE_MAX_TEXT_CHARS]


def _format_profile(profile: dict[str, Any]) -> str:
    env = (
        profile.get("environment")
        if isinstance(profile.get("environment"), dict)
        else {}
    )
    prefs = (
        profile.get("preferences")
        if isinstance(profile.get("preferences"), list)
        else []
    )
    consts = (
        profile.get("constraints")
        if isinstance(profile.get("constraints"), list)
        else []
    )

    parts = ["[USER PROFILE]"]
    if env:
        env_items = []
        for k in ("os", "shell", "editor"):
            v2 = _clip(env.get(k))
            if v2:
                env_items.append(f"{k}={v2}")
        if env_items:
            parts.append("Environment: " + "; ".join(env_items))
    if prefs:
        pref_items = [_clip(x) for x in prefs[-PROFILE_MAX_ITEMS:]]
        pref_items = [x for x in pref_items if x]
        if pref_items:
            parts.append("Preferences: " + "; ".join(pref_items))
    if consts:
        const_items = [_clip(x) for x in consts[-PROFILE_MAX_ITEMS:]]
        const_items = [x for x in const_items if x]
        if const_items:
            parts.append("Constraints: " + "; ".join(const_items))
    return "\n".join(parts)


def append_long_memory_system_messages(
    *,
    core: Any,
    messages: list[dict[str, Any]],
    build_long_memory_system_message_fn: Callable[[Any], dict[str, Any]],
    personal_long_memory_mod: Any,
    shared_memory_mod: Any,
) -> dict[str, bool]:
    # Inject user profile if profiling is enabled and profile exists
    try:
        from .profile_manager import is_profiling_enabled, load_profile

        if is_profiling_enabled():
            profile = load_profile()
            if (
                profile.get("environment")
                or profile.get("preferences")
                or profile.get("constraints")
            ):
                profile_msg = {"role": "system", "content": _format_profile(profile)}
                messages.append(profile_msg)
                core.log_message(profile_msg)
    except Exception:
        pass
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

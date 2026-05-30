"""Runtime helpers for injecting learned profile and long-term memory into prompts."""

from __future__ import annotations

from typing import Any, Callable

from .profile_manager import PROFILE_MAX_ITEMS, PROFILE_MAX_TEXT_CHARS


def _clip(text: Any) -> str:
    return " ".join(str(text).split()).strip()[:PROFILE_MAX_TEXT_CHARS]


def _profile_key(text: Any) -> str:
    return " ".join(str(text).split()).strip().casefold()


def _format_profile(profile: dict[str, Any]) -> str:
    """Render the learned profile in a compact, deduplicated, LLM-friendly form."""
    env_source = profile.get("environment")
    env = env_source if isinstance(env_source, dict) else {}
    prefs_source = profile.get("preferences")
    prefs = prefs_source if isinstance(prefs_source, list) else []
    consts_source = profile.get("constraints")
    consts = consts_source if isinstance(consts_source, list) else []

    blocks = ["[USER PROFILE]"]
    seen: set[str] = set()

    env_lines: list[str] = []
    for key in ("os", "shell", "editor"):
        value = _clip(env.get(key))
        if not value:
            continue
        value_key = _profile_key(value)
        if not value_key or value_key in seen:
            continue
        seen.add(value_key)
        seen.add(_profile_key(f"{key}: {value}"))
        env_lines.append(f"  - {key}: {value}")
    if env_lines:
        blocks.append("Environment:\n" + "\n".join(env_lines))

    def _append_section(title: str, values: list[Any]) -> None:
        lines: list[str] = []
        for raw_value in values[-PROFILE_MAX_ITEMS:]:
            text = _clip(raw_value)
            if not text:
                continue
            key = _profile_key(text)
            if not key or key in seen:
                continue
            seen.add(key)
            lines.append(f"  - {text}")
        if lines:
            blocks.append(f"{title}:\n" + "\n".join(lines))

    # Constraints first so guardrails are seen before softer preferences.
    _append_section("Constraints", consts)
    _append_section("Preferences", prefs)
    return "\n\n".join(blocks)


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

    # Inject user profile if profiling is enabled and profile exists.
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

"""Runtime invalidation triggered by explicit personal-memory forget operations."""

from __future__ import annotations

from typing import Any


def memory_generation(core: Any) -> int:
    """Return the current in-process memory generation."""
    try:
        return max(0, int(getattr(core, "memory_generation", 0) or 0))
    except (TypeError, ValueError):
        return 0


def forgotten_memory_system_contents(core: Any) -> set[str]:
    """Return startup personal-memory projections invalidated by forgets."""
    values = getattr(core, "_uagent_forgotten_memory_system_contents", set()) or set()
    if not isinstance(values, (set, list, tuple)):
        return set()
    return {str(value) for value in values if str(value)}


def _registered_personal_memory_contents(core: Any) -> set[str]:
    registry = getattr(core, "_uagent_memory_system_contents", {}) or {}
    if not isinstance(registry, dict):
        return set()
    values = registry.get("personal", set())
    if not isinstance(values, (set, list, tuple)):
        return set()
    return {str(value) for value in values if str(value)}


def _purge_session_memory_projections(core: Any) -> None:
    """Best-effort physical cleanup of derived context from durable sessions."""
    store = getattr(core, "session_store", None)
    if store is None:
        return
    list_messages = getattr(
        store, "_uagent_memory_original_list_messages", None
    ) or getattr(store, "list_messages", None)
    replace_messages = getattr(
        store, "_uagent_memory_original_replace_messages", None
    ) or getattr(store, "replace_messages", None)
    if not callable(list_messages) or not callable(replace_messages):
        return
    try:
        from .memory_history_boundary import strip_derived_memory_context

        sessions = list(store.list_sessions())
    except Exception:
        return
    for row in sessions:
        session_id = str(row.get("session_id") or "")
        if not session_id:
            continue
        try:
            messages = list(list_messages(session_id))
            filtered = strip_derived_memory_context(messages)
            if len(filtered) != len(messages):
                replace_messages(session_id, filtered)
        except Exception:
            continue


def invalidate_memory_runtime(core: Any | None = None) -> int:
    """Invalidate memory-derived runtime state after a successful forget.

    Forgetting persisted memory must also make any turn-local projection and
    provider continuation unusable. The generation counter lets projection
    application reject a snapshot that was captured before the forget even if
    a caller still holds a reference to it.
    """
    if core is None:
        from .. import core as core_module

        core = core_module

    next_generation = memory_generation(core) + 1
    invalidated_contents = (
        forgotten_memory_system_contents(core)
        | _registered_personal_memory_contents(core)
    )
    try:
        core.memory_generation = next_generation
        # Snapshot only the startup Personal Memory blocks that existed before
        # this forget. A later room/startup may register fresh memory content;
        # it must not be hidden merely because an earlier forget occurred.
        core._uagent_forgotten_memory_system_contents = invalidated_contents
    except Exception:
        pass

    # Older runtimes could persist transient Memory/Profile system blocks in
    # SessionStore. Remove those derived rows through the unfiltered raw store
    # methods so they cannot survive a restart, search index, or later rewrite.
    _purge_session_memory_projections(core)

    # These objects can contain, or point at, memory-derived provider input.
    for name in (
        "memory_projection_snapshot",
        "context_plan",
        "context_projection_id",
    ):
        try:
            setattr(core, name, None)
        except Exception:
            pass

    # Shadow observations contain metadata only, but clearing them prevents
    # diagnostics from presenting pre-forget candidate IDs as current state.
    try:
        core.memory_shadow_last_observation = None
        core.memory_shadow_observations = []
    except Exception:
        pass

    # Gemini/Vertex cached content may contain a prior memory projection.
    try:
        core._gemini_cache_needs_refresh = True
    except Exception:
        pass

    # Responses API continuation can retain provider-side context that no
    # longer matches local memory state. Clear both the runtime object and the
    # compatibility state dictionary without touching durable conversation
    # history.
    runtime = getattr(core, "responses_runtime", None)
    clear_runtime = getattr(runtime, "clear_continuation", None)
    if callable(clear_runtime):
        try:
            clear_runtime("memory_forget")
        except Exception:
            pass

    clear_responses = getattr(core, "clear_responses_continuation", None)
    if callable(clear_responses):
        try:
            clear_responses()
        except Exception:
            pass

    state = getattr(core, "responses_state", None)
    if isinstance(state, dict):
        state.pop("previous_response_id", None)
        state.pop("active_response_id", None)
        state.pop("_stale_rid_occurred", None)

    return next_generation


__all__ = [
    "forgotten_memory_system_contents",
    "invalidate_memory_runtime",
    "memory_generation",
]

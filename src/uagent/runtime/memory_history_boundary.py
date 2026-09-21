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
    forgotten = (
        getattr(core, "_uagent_forgotten_memory_system_contents", set()) or set()
    )
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


def _is_durable_history_summary(message: Any) -> bool:
    """Return True for a history-compression summary that must stay durable."""
    if not isinstance(message, dict):
        return False
    try:
        from ..llm_message_helpers import _is_history_summary_message

        return bool(_is_history_summary_message(message))
    except Exception:
        return False


def strip_derived_memory_context(
    messages: Sequence[dict[str, Any]],
    *,
    core: Any | None = None,
) -> list[dict[str, Any]]:
    """Remove derived memory context from a durable/restored message sequence.

    New profile/evidence projections have explicit reserved prefixes. Older
    Personal/Shared Memory blocks did not have a stable marker, but startup
    ordering is stable: ``build_initial_messages`` inserts the startup CWD
    marker at the end of the durable leading system block and memory/profile
    blocks are appended afterwards. Therefore system messages between that
    startup marker and the first conversational message are legacy derived
    context, except for explicitly durable runtime markers and conversation
    summaries produced by history compression.
    """
    items = [message for message in messages if isinstance(message, dict)]
    first_conversation = next(
        (
            index
            for index, message in enumerate(items)
            if message.get("role") != "system"
        ),
        len(items),
    )
    startup_cwd_index: int | None = None
    for index, message in enumerate(items[:first_conversation]):
        if _is_startup_cwd_message(message):
            startup_cwd_index = index

    filtered: list[dict[str, Any]] = []
    for index, message in enumerate(items):
        if is_runtime_memory_system_message(message, core=core):
            continue
        if (
            startup_cwd_index is not None
            and startup_cwd_index < index < first_conversation
            and message.get("role") == "system"
        ):
            if _is_durable_history_summary(message):
                filtered.append(message)
                continue
            content = str(message.get("content") or "")
            if not content.startswith(_DURABLE_RUNTIME_PREFIXES):
                continue
        filtered.append(message)
    return filtered


def install_session_store_memory_boundary(core: Any) -> None:
    """Wrap one attached SessionStore so derived context stays transient.

    This is intentionally an instance-level rollout adapter: it avoids a
    storage-schema migration while protecting all in-process SessionStore
    consumers, including history compression and profile reconstruction.
    Raw methods are retained on the instance for privacy cleanup code that
    must physically remove legacy derived rows.
    """
    store = getattr(core, "session_store", None)
    if store is None:
        return
    if getattr(store, "_uagent_memory_boundary_installed", False):
        return

    list_messages = getattr(store, "list_messages", None)
    replace_messages = getattr(store, "replace_messages", None)
    search = getattr(store, "search", None)
    if not callable(list_messages) or not callable(replace_messages):
        return

    def bounded_list_messages(session_id: str) -> list[dict[str, Any]]:
        return strip_derived_memory_context(list_messages(session_id), core=core)

    def bounded_replace_messages(
        session_id: str, messages: list[dict[str, Any]]
    ) -> None:
        replace_messages(
            session_id,
            strip_derived_memory_context(messages, core=core),
        )

    try:
        store._uagent_memory_original_list_messages = list_messages
        store._uagent_memory_original_replace_messages = replace_messages
        store.list_messages = bounded_list_messages
        store.replace_messages = bounded_replace_messages
        if callable(search):
            store._uagent_memory_original_search = search

            def bounded_search(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
                try:
                    target_limit = max(1, int(kwargs.get("limit", 20)))
                except (TypeError, ValueError):
                    target_limit = 20

                fetch_limit = max(64, target_limit)
                while True:
                    search_kwargs = dict(kwargs)
                    search_kwargs["limit"] = fetch_limit
                    rows = search(*args, **search_kwargs)
                    durable_systems: dict[str, set[str]] = {}
                    filtered: list[dict[str, Any]] = []

                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        if str(row.get("role") or "") == "system":
                            if is_runtime_memory_system_message(row, core=core):
                                continue
                            session_id = str(row.get("session_id") or "")
                            if session_id:
                                if session_id not in durable_systems:
                                    try:
                                        durable_messages = strip_derived_memory_context(
                                            list_messages(session_id), core=core
                                        )
                                    except Exception:
                                        durable_messages = []
                                    durable_systems[session_id] = {
                                        str(message.get("content") or "")
                                        for message in durable_messages
                                        if message.get("role") == "system"
                                    }
                                if str(row.get("content") or "") not in durable_systems[
                                    session_id
                                ]:
                                    continue
                        filtered.append(row)
                        if len(filtered) >= target_limit:
                            return filtered[:target_limit]

                    if len(rows) < fetch_limit or fetch_limit >= 10_000:
                        return filtered[:target_limit]
                    fetch_limit = min(10_000, fetch_limit * 4)

            store.search = bounded_search
        store._uagent_memory_boundary_installed = True
    except Exception:
        pass


__all__ = [
    "install_session_store_memory_boundary",
    "is_runtime_memory_system_message",
    "registered_memory_system_contents",
    "strip_derived_memory_context",
]

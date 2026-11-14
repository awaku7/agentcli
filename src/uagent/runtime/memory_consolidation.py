"""Background consolidation of long-term memory from conversation logs.

The conversational agent saves durable notes as they come up, but some
are missed. This pass re-reads the conversation in a background thread
(the same shape as profile learning, ``run_profiling_async``), asks the
model for durable facts, decisions and commitments, and saves them
through the checked save path with ``source="consolidation"``.

The pass fires when history is compressed, and — so ordinary sessions
that never grow long enough to compress are covered too — when a
session ends: on a session switch (the outgoing conversation is
consolidated before it is replaced) and at startup, where the newest
previous session in the same project is caught up once from its stored
messages if the process exited before any switch happened. Session-end
passes are gated on a minimum of user turns and a per-session
watermark, so an unchanged session never costs a second provider call.

Two boundaries keep the pass safe:

- It only runs under the local identity. The checked save path writes
  to the legacy unscoped store, which is fenced to local mode; scoped
  Web memory is written through the agent tools instead.
- It can never resurrect a forgotten note. Saves carry a
  content-derived ``source_id``, and the checked save path refuses
  background sources whose content matches a tombstone.

Saved counts are kept in a small state file next to the memory file
and surfaced once, the next time a session prints pending memory
notices. Opt out with ``UAGENT_MEMORY_CONSOLIDATION=0`` (or the master
``UAGENT_MEMORY=0``).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from ..env_utils import env_get

_MAX_NOTES_PER_PASS = 5
_STATE_FILE_NAME = "memory_consolidation_state.json"
_MIN_USER_TURNS_FOR_SESSION_END = 2

# Sessions with a consolidation pass already in flight, by session id.
# Guards the session-end triggers (switch / startup catch-up) and the
# compression hook from piling duplicate provider calls onto the same
# conversation.
_in_flight_lock = threading.Lock()
_in_flight_sessions: set[str] = set()

# Serializes read-modify-write cycles on the state file: pending-notice
# accounting runs on worker threads while session-end watermarks are
# marked on foreground threads, and unsynchronized cycles lose updates.
_state_lock = threading.Lock()

_EXTRACTION_PROMPT = (
    "You are a memory consolidation agent. Analyze the conversation log "
    "and extract facts about the user that are worth keeping in "
    "long-term memory across sessions:\n"
    "- durable personal facts (who they are, where they live or work, "
    "the people and projects that matter to them)\n"
    "- decisions they made and commitments they took on\n\n"
    "Do NOT include preferences, habits or constraints (those belong "
    "to the user profile, not long-term memory).\n"
    "Do NOT include one-off task details, temporary questions, "
    "chit-chat, or sensitive credentials.\n"
    "Only include facts the user themselves stated or clearly "
    "confirmed.\n"
    "Write each note as one short sentence in the same language as "
    "the conversation.\n"
    "You MUST respond ONLY with a valid JSON object matching this "
    "schema:\n"
    '{"notes": ["string"]}\n'
    'If nothing is worth keeping, respond with {"notes": []}.'
)


def consolidation_enabled() -> bool:
    """Whether the background consolidation pass is active."""
    master = (env_get("UAGENT_MEMORY") or "").strip().lower()
    if master in ("0", "false", "no", "off"):
        return False
    value = (env_get("UAGENT_MEMORY_CONSOLIDATION") or "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def consolidation_source_id(note: str) -> str:
    """Stable origin id for one consolidated note (content-derived)."""
    digest = hashlib.sha256(str(note).encode("utf-8")).hexdigest()
    return f"consolidation:{digest}"


def save_consolidation_notes(
    notes: list[str], *, owner: str = "", project: str = ""
) -> int:
    """Save extracted notes through the checked save path.

    Returns how many notes were newly saved. Duplicates, secrets and
    notes matching a tombstone are refused by the save path itself.
    ``owner``/``project`` pin the scope captured when the pass was
    launched; the save path would otherwise resolve the project at
    save time (from the process CWD) and could file the notes under
    whatever project is current when the background thread finishes.
    """
    from ..tools.long_memory import save_long_memory

    saved = 0
    for raw in notes[:_MAX_NOTES_PER_PASS]:
        note = str(raw or "").strip()
        if not note:
            continue
        result = save_long_memory(
            note,
            owner=owner,
            project=project,
            source="consolidation",
            source_id=consolidation_source_id(note),
        )
        if result.get("saved"):
            saved += 1
    if saved:
        _record_pending_notice(saved)
    return saved


def run_memory_consolidation_async(
    messages: list[dict[str, Any]], core: Any, *, session_id: str = ""
) -> None:
    """Run one consolidation pass over ``messages`` in a background thread.

    ``session_id`` names the session the messages belong to when the
    caller is a session-end trigger: a per-session watermark in the
    state file then suppresses repeat passes over an unchanged
    session, and the pass is marked before the thread starts so a
    burst of triggers (switch, startup, compression) cannot queue
    duplicate provider calls for the same conversation.
    """
    if not consolidation_enabled():
        return
    if not messages:
        return
    try:
        from .identity_context import current_turn_is_local

        if not current_turn_is_local():
            return
    except Exception:
        return
    flight_key = session_id or str(getattr(core, "_session_store_active_id", "") or "")
    with _in_flight_lock:
        if flight_key and flight_key in _in_flight_sessions:
            return
        if session_id and _consolidated_message_count(session_id) >= len(messages):
            return
        if flight_key:
            _in_flight_sessions.add(flight_key)
    if session_id:
        _mark_session_consolidated(session_id, len(messages))
    # Deep copy messages to avoid thread-safety issues with the main loop
    try:
        messages_copy = json.loads(json.dumps(messages))
    except Exception:
        with _in_flight_lock:
            _in_flight_sessions.discard(flight_key)
        return
    # Capture the memory scope now: the worker thread runs later, and
    # resolving the project at save time would use whatever directory
    # or session is current then, not the one this conversation is in.
    owner = ""
    project = ""
    try:
        from .memory_scope import resolve_memory_owner, resolve_memory_project

        owner = resolve_memory_owner()
        project = resolve_memory_project()
    except Exception:
        owner = ""
        project = ""
    thread = threading.Thread(
        target=_run_worker_tracked,
        args=(messages_copy, core, owner, project, flight_key),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        with _in_flight_lock:
            _in_flight_sessions.discard(flight_key)
        raise


def _run_worker_tracked(
    messages: list[dict[str, Any]],
    core: Any,
    owner: str,
    project: str,
    flight_key: str,
) -> None:
    """Run the consolidation worker and release its in-flight slot."""
    try:
        _consolidation_worker(messages, core, owner, project)
    finally:
        if flight_key:
            with _in_flight_lock:
                _in_flight_sessions.discard(flight_key)


def _user_turn_count(messages: list[dict[str, Any]]) -> int:
    return sum(
        1
        for message in messages or []
        if isinstance(message, dict) and message.get("role") == "user"
    )


def run_session_end_consolidation(
    messages: list[dict[str, Any]], core: Any, *, session_id: str = ""
) -> None:
    """Consolidate a session that is ending (switch or startup catch-up).

    Session-end triggers stay cheap: disabled and trivial sessions
    return before any copying, and the per-session watermark in
    :func:`run_memory_consolidation_async` keeps an unchanged session
    from costing a second provider call.
    """
    if not consolidation_enabled():
        return
    if _user_turn_count(messages) < _MIN_USER_TURNS_FOR_SESSION_END:
        return
    sid = session_id or str(getattr(core, "_session_store_active_id", "") or "")
    if not sid:
        return
    run_memory_consolidation_async(messages, core, session_id=sid)


def run_startup_consolidation(
    core: Any, store: Any, *, current_session_id: str = ""
) -> None:
    """Catch up the previous session when a session store attaches.

    Sessions that ended because the process exited (or crashed) never
    hit the switch trigger; the newest other session in the same
    project is consolidated once, from its stored messages, the next
    time a store attaches. Only that one session is considered — in
    the normal chain each startup handles the session right before
    it — and everything here is best-effort and off the foreground
    path beyond two small store reads.
    """
    try:
        if not consolidation_enabled() or store is None:
            return
        rows = store.list_sessions()
        candidate: dict[str, Any] | None = None
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("session_id") or "")
            if not sid or sid == current_session_id:
                continue
            if str(row.get("entry_point") or "") == "sub-agent":
                continue
            candidate = row
            break
        if candidate is None:
            return
        sid = str(candidate.get("session_id") or "")
        try:
            from .memory_scope import resolve_memory_project

            if str(candidate.get("project") or "") != resolve_memory_project():
                return
        except Exception:
            return
        messages = store.list_messages(sid) or []
        if messages and _consolidated_message_count(sid) >= len(messages):
            return
        run_session_end_consolidation(messages, core, session_id=sid)
    except Exception:
        pass


def _consolidation_worker(
    messages: list[dict[str, Any]],
    core: Any,
    owner: str = "",
    project: str = "",
) -> None:
    """Background worker: extract durable notes and save them."""
    try:
        from ..profile_manager import _llm_simple_text, _sanitize_log_for_profiling
        from ..providers import util_providers

        provider, client, model_name = util_providers.make_client(core)
        if not client:
            return
        sanitized_log = _sanitize_log_for_profiling(messages)
        if not sanitized_log.strip():
            return
        raw_response = _llm_simple_text(
            provider=provider,
            client=client,
            model_name=model_name,
            system_prompt=_EXTRACTION_PROMPT,
            user_prompt=f"CONVERSATION LOG:\n{sanitized_log}",
            max_tokens=1200,
            temperature=0.0,
        )
        notes = _parse_notes(raw_response)
        if notes:
            save_consolidation_notes(notes, owner=owner, project=project)
    except Exception:
        # Fail silently in background thread to avoid interrupting the user
        pass


def _parse_notes(raw_response: str) -> list[str]:
    """Parse the extraction response into a list of note strings."""
    cleaned = str(raw_response or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        payload = json.loads(cleaned)
    except Exception:
        return []
    items = payload.get("notes") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    return [
        str(item).strip()
        for item in items
        if isinstance(item, str) and str(item).strip()
    ]


def _state_path() -> Path:
    from ..tools.long_memory import get_memory_file_path

    return Path(get_memory_file_path()).expanduser().parent / _STATE_FILE_NAME


def _load_state() -> dict[str, Any]:
    try:
        payload = json.loads(_state_path().read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_state(state: dict[str, Any]) -> None:
    try:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = time.time()
        path.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _consolidated_message_count(session_id: str) -> int:
    """How many messages of ``session_id`` a pass has already covered."""
    try:
        sessions = _load_state().get("sessions")
        if isinstance(sessions, dict):
            entry = sessions.get(session_id)
            if isinstance(entry, dict):
                return int(entry.get("count") or 0)
    except Exception:
        pass
    return 0


def _mark_session_consolidated(session_id: str, message_count: int) -> None:
    with _state_lock:
        state = _load_state()
        sessions = state.get("sessions")
        if not isinstance(sessions, dict):
            sessions = {}
        sessions[session_id] = {"count": int(message_count), "at": time.time()}
        state["sessions"] = sessions
        _write_state(state)


def _record_pending_notice(saved_count: int) -> None:
    """Accumulate auto-saved counts until they are shown to the user."""
    with _state_lock:
        state = _load_state()
        try:
            pending = int(state.get("pending_saved") or 0)
        except Exception:
            pending = 0
        state["pending_saved"] = pending + saved_count
        _write_state(state)


def pop_pending_consolidation_count() -> int:
    """Return and clear the number of auto-saved notes not yet shown."""
    with _state_lock:
        state = _load_state()
        try:
            count = int(state.get("pending_saved") or 0)
        except Exception:
            count = 0
        if count:
            state["pending_saved"] = 0
            _write_state(state)
        return count

"""Immediate save for explicitly marked memory notes.

Users can prefix a message with ``remember:`` or ``記憶：`` to ask for a
note to be kept. Historically those markers were only collected as
candidates that a human had to approve with ``:sessions approve``; the
agent-managed memory design saves them immediately at write time
instead. This module is the fallback path for models that do not call
the memory tools reliably: detection happens when the message is
written to the session store, the save goes through the same checked
save path as the tools, and re-writes of the same history cannot save
the same marker twice (nor resurrect it after it was forgotten),
because the save is keyed by a content-derived ``source_id``.

Opt out with ``UAGENT_MEMORY_MARKER=0`` (or the master
``UAGENT_MEMORY=0``). Under the local identity the note lands in the
legacy unscoped store; non-local Web turns are fenced off from that
store the same way the legacy memory API is, but an authenticated
principal in a private Web session saves into their own scoped
personal memory instead.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..env_utils import env_get

_MARKER_PREFIXES = ("remember:", "記憶：", "記憶:")


def extract_memory_marker(content: str) -> str | None:
    """Return the note text after a leading memory marker, or None."""
    text = str(content or "")
    lowered = text.lower()
    for prefix in _MARKER_PREFIXES:
        if lowered.startswith(prefix):
            value = text[len(prefix) :].strip()
            return value or None
    return None


def marker_enabled() -> bool:
    """Whether the string-marker fallback is active."""
    master = (env_get("UAGENT_MEMORY") or "").strip().lower()
    if master in ("0", "false", "no", "off"):
        return False
    value = (env_get("UAGENT_MEMORY_MARKER") or "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def marker_source_id(note: str) -> str:
    """Stable origin id for one marked note (content-derived)."""
    digest = hashlib.sha256(str(note).encode("utf-8")).hexdigest()
    return f"marker:{digest}"


def _local_identity_turn() -> bool:
    """Whether the current turn runs under the local identity.

    Marker saves land in the legacy (unscoped) memory store, whose owner
    resolves to the server's OS login, and the Web memory API fences
    that store to local mode (``_legacy_local_only``). The marker
    fallback keeps the same boundary: it fires only when there is no
    turn context (plain local entry points) or the turn's identity is
    the local one. Non-local Web identities (token, OIDC, browser
    guests) never write local memory as a side effect of message
    logging; private-session principals use their scoped store
    instead (see :func:`_save_scoped_marker`).
    """
    try:
        from .identity_context import current_turn_is_local

        return current_turn_is_local()
    except Exception:
        return True


def save_memory_marker(content: str) -> dict[str, Any] | None:
    """Save the marked note in ``content`` immediately, if it has a marker.

    Returns the save result dict when a marker was present (saved or
    not), or None when the message carries no marker or the fallback is
    disabled. Never raises: the marker path must not break message
    logging.
    """
    if not marker_enabled():
        return None
    note = extract_memory_marker(content)
    if note is None:
        return None
    if not _local_identity_turn():
        return _save_scoped_marker(note)
    try:
        from ..tools.long_memory import save_long_memory

        return save_long_memory(note, source="marker", source_id=marker_source_id(note))
    except Exception:
        return {"saved": False, "reason": "error", "memory_id": ""}


def _save_scoped_marker(note: str) -> dict[str, Any] | None:
    """Save a marked note into the turn principal's scoped personal memory.

    Non-local turns cannot write the legacy unscoped store (see
    :func:`_local_identity_turn`), but an authenticated principal in a
    private session has a scoped store of their own. The same screens
    as the checked save path apply (length, credentials) and duplicates
    are refused. The scoped store forgets by hard deletion, so — as in
    the scoped Web API itself — a marker repeated after a forget saves
    again; there is no tombstone to match against. Room (non-private)
    turns and the JSONL backend have no scoped personal store to write
    to, so they return None (no save), keeping the local-only fence
    for them.
    """
    try:
        from .identity_context import get_current_turn_context

        turn = get_current_turn_context()
        if turn is None or not turn.authenticated or not turn.private_session:
            return None
        from ..tools.long_memory import (
            NOTE_MAX_CHARS,
            _sqlite_path,
            _use_sqlite,
            looks_like_secret,
            note_key_for,
        )

        if not _use_sqlite():
            return None
        text = str(note or "").strip()
        if not text or len(text) > NOTE_MAX_CHARS or looks_like_secret(text):
            return {"saved": False, "reason": "screened", "memory_id": ""}
        from .memory_access import MemoryAccessContext, ScopedMemoryStore
        from .memory_store import open_memory_store

        store = open_memory_store(_sqlite_path())
        try:
            context = MemoryAccessContext.from_turn(turn, private_session=True)
            scoped = ScopedMemoryStore(store, context)
            key = note_key_for(text)
            for record in scoped.records():
                if note_key_for(str(record.get("note") or "")) == key:
                    return {
                        "saved": False,
                        "reason": "duplicate",
                        "memory_id": str(record.get("memory_id") or ""),
                    }
            record = scoped.append(text)
            return {
                "saved": True,
                "reason": "saved",
                "memory_id": str(record.get("memory_id") or ""),
            }
        finally:
            store.close()
    except Exception:
        return None

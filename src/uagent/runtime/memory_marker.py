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
``UAGENT_MEMORY=0``).
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
    try:
        from ..tools.long_memory import save_long_memory

        return save_long_memory(note, source="marker", source_id=marker_source_id(note))
    except Exception:
        return {"saved": False, "reason": "error", "memory_id": ""}

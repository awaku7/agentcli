"""State history tracking for Matter devices.

Records state changes over time and provides query capabilities.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

_MAX_ENTRIES = 10000

# In-memory buffer: list of dicts
_history: list[dict[str, Any]] = []


def _max_entries() -> int:
    try:
        return max(100, int(os.getenv("UAGENT_MATTER_STATE_HISTORY_MAX", str(_MAX_ENTRIES))))
    except (ValueError, TypeError):
        return _MAX_ENTRIES


def record_state_change(device_id: str, attribute: str, old_value: Any, new_value: Any) -> None:
    """Record a state change event in the history."""
    global _history
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "dev": device_id,
        "attribute": attribute,
        "old": old_value,
        "new": new_value,
    }
    _history.append(entry)
    # Trim oldest entries if over limit
    limit = _max_entries()
    if len(_history) > limit:
        _history = _history[-limit:]


def query_history(
    device_id: str | None = None,
    attribute: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query state history with optional filters."""
    results = list(_history)

    if device_id:
        dk = device_id.strip().casefold()
        results = [e for e in results if str(e.get("dev") or "").casefold() == dk]

    if attribute:
        ak = attribute.strip().casefold()
        results = [e for e in results if str(e.get("attribute") or "").casefold() == ak]

    if since:
        results = [e for e in results if e.get("ts", "") >= since]

    if until:
        results = [e for e in results if e.get("ts", "") <= until]

    return results[-limit:]


def clear_history() -> int:
    """Clear all history entries. Returns the number of cleared entries."""
    global _history
    count = len(_history)
    _history.clear()
    return count


def history_count() -> int:
    """Return the current number of history entries."""
    return len(_history)

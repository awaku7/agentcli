"""In-process OTLP delivery observations for the :otel command.

No files, network probes, background jobs or captured request content.
All states describe the local SDK/exporter; no claim about Admin availability.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable

_STATES = frozenset(
    {
        "disabled",
        "dependencies_unavailable",
        "backend_unavailable",
        "backend_initialization_failed",
        "no_endpoint",
        "awaiting_export",
        "sent",
        "failed",
        "retry_cooldown",
    }
)
_LOCK = threading.Lock()
_CURRENT: dict[str, str | bool | None] = {
    "enabled": False,
    "state": "disabled",
    "last_attempt_utc": None,
    "last_success_utc": None,
    "last_failure_utc": None,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def update_delivery_status(state: str, *, enabled: bool = True) -> None:
    """Record only local, bounded export outcome; never interrupt UAG work."""
    if state not in _STATES:
        return
    try:
        with _LOCK:
            if state == "disabled":
                _CURRENT.update(
                    last_attempt_utc=None,
                    last_success_utc=None,
                    last_failure_utc=None,
                )
            _CURRENT["enabled"] = bool(enabled)
            _CURRENT["state"] = state
            if state in {"sent", "failed"}:
                now = _utc_now()
                _CURRENT["last_attempt_utc"] = now
                _CURRENT[
                    "last_success_utc" if state == "sent" else "last_failure_utc"
                ] = now
    except Exception:
        pass


def delivery_status_snapshot() -> dict[str, str | bool | None]:
    """Return immutable-by-copy state for current UAG process."""
    with _LOCK:
        return dict(_CURRENT)


def format_delivery_status(*, tr: Callable[[str], str] | None = None) -> str:
    """Human-readable state in the current host UI locale, without secrets."""
    if tr is None:
        from ...i18n import _

        tr = _
    snapshot = delivery_status_snapshot()
    label = "ON" if snapshot["enabled"] else "OFF"
    return "\n".join(
        (
            tr("OTel: %(value)s") % {"value": label},
            tr("Delivery: %(value)s") % {"value": snapshot["state"]},
            tr("Last export attempt (UTC): %(value)s")
            % {"value": snapshot["last_attempt_utc"] or "-"},
            tr("Last success (UTC): %(value)s")
            % {"value": snapshot["last_success_utc"] or "-"},
            tr("Last failure (UTC): %(value)s")
            % {"value": snapshot["last_failure_utc"] or "-"},
            tr("Local exporter observation; Admin receipt is not confirmed."),
        )
    )

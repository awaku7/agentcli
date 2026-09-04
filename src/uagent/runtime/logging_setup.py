"""Structured event logging helpers for adapter boundaries."""

from __future__ import annotations

import json
import logging
import math
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from .tool_result_persistence import sanitize_message_for_history

_LOGGER = logging.getLogger("uagent.events")
_SECRET_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization_code",
}
_EVENT_CONTEXT: ContextVar[dict[str, Any]] = ContextVar(
    "uagent_event_context", default={}
)
_EVENT_SCHEMA_VERSION = "1"
_COMMON_EVENT_FIELDS = (
    "agent_id",
    "session_id",
    "task_id",
    "tool_call_id",
    "provider",
    "duration_ms",
    "error_type",
)
_EVENT_CATEGORY_FIELDS = {
    "agent": ("updated_at",),
    "a2a": ("task_id", "duration_ms", "error_type"),
    "task": ("task_id", "duration_ms", "error_type"),
    "tool": ("tool", "tool_call_id", "duration_ms", "error_type"),
    "llm": ("provider", "model", "duration_ms", "error_type"),
    "credential": ("credential_name", "found", "deleted", "metadata", "error_type"),
    "oauth": ("issuer", "resource", "provider", "duration_ms", "error_type"),
    "computer": ("action_id", "duration_ms", "error_type"),
}


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def bind_event_context(**fields: Any):
    """Bind correlation fields for the lifetime of the current execution entrypoint."""
    current = dict(_EVENT_CONTEXT.get())
    current.update({key: value for key, value in fields.items() if value is not None})
    current.setdefault("correlation_id", str(uuid4()))
    return _EVENT_CONTEXT.set(current)


def reset_event_context(token: Any) -> None:
    """Restore the event context returned by :func:`bind_event_context`."""
    _EVENT_CONTEXT.reset(token)


@contextmanager
def event_context(**fields: Any) -> Iterator[None]:
    """Temporarily add correlation fields to all structured events."""
    current = dict(_EVENT_CONTEXT.get())
    current.update({key: value for key, value in fields.items() if value is not None})
    token = _EVENT_CONTEXT.set(current)
    try:
        yield
    finally:
        _EVENT_CONTEXT.reset(token)


def _safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        key: "[REDACTED]" if key.lower() in _SECRET_KEYS else value
        for key, value in fields.items()
    }


def _normalize_duration(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric < 0:
        return None
    return int(numeric) if numeric.is_integer() else round(numeric, 3)


def append_masked_message(log_file: str, message: dict[str, Any], mask_fn: Any) -> None:
    """Append one masked JSONL message without owning session state."""
    import os

    try:
        masked = sanitize_message_for_history(mask_fn(message))
        directory = os.path.dirname(log_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(masked, ensure_ascii=False) + "\n")
    except Exception:
        pass


def log_event(event_code: str, **fields: Any) -> None:
    """Emit a stable event code with secret fields removed."""
    context = dict(_EVENT_CONTEXT.get())
    context.setdefault("schema_version", _EVENT_SCHEMA_VERSION)
    context.setdefault("event_id", str(uuid4()))
    context.setdefault("correlation_id", str(uuid4()))
    context.setdefault("timestamp", _now_iso())
    context.setdefault("status", "event")
    # Event codes and field names are machine-readable and must never be
    # localized. Only human-facing consumers translate their own messages.
    payload = {**context, **fields}
    payload["schema_version"] = _EVENT_SCHEMA_VERSION
    payload["event_code"] = event_code
    for field_name in _COMMON_EVENT_FIELDS:
        payload.setdefault(field_name, None)
    payload["duration_ms"] = _normalize_duration(payload.get("duration_ms"))
    category = event_code.split(".", 1)[0]
    for field_name in _EVENT_CATEGORY_FIELDS.get(category, ()):
        payload.setdefault(field_name, None)
    _LOGGER.info(
        json.dumps(
            _safe_fields(payload), ensure_ascii=False, sort_keys=True, default=str
        )
    )

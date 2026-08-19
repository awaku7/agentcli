"""Structured event logging helpers for adapter boundaries."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

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


def append_masked_message(log_file: str, message: dict[str, Any], mask_fn: Any) -> None:
    """Append one masked JSONL message without owning session state."""
    import os

    try:
        masked = mask_fn(message)
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
    payload = {**context, "event_code": event_code, **fields}
    _LOGGER.info(
        json.dumps(
            _safe_fields(payload), ensure_ascii=False, sort_keys=True, default=str
        )
    )

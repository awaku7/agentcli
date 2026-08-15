"""Structured Computer Use audit events and in-memory sink."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    phase: str
    action_id: str
    session_id: str | None = None
    turn_id: str | None = None
    action: str | None = None
    provider: str | None = None
    model: str | None = None
    environment: str | None = None
    success: bool | None = None
    error: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class InMemoryAuditSink:
    """Deterministic audit sink for tests and local dry-run sessions."""

    events: list[AuditEvent] = field(default_factory=list)

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


def make_audit_event(
    *,
    phase: str,
    action: Any,
    session_id: str | None,
    turn_id: str | None,
    success: bool | None = None,
    error: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        phase=phase,
        action_id=action.action_id,
        session_id=session_id,
        turn_id=turn_id,
        action=action.action,
        provider=action.provider or None,
        success=success,
        error=error,
    )

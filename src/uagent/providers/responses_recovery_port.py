"""Responses API implementation of the provider-neutral recovery port.

The port owns provider I/O while recovery planning remains provider-neutral.
It does not modify persistent conversation history; only remote Responses
state and recovery-journal metadata are touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from ..runtime.context_recovery import (
    RecoveryPlan,
    RemoteMutationStatus,
    RemoteRecoveryPort,
    RemoteSessionUpdate,
)
from .responses_manager import ResponsesManager


class RecoveryJournal(Protocol):
    """Minimal metadata-only journal needed for idempotent remote recovery."""

    def lookup(self, recovery_id: str) -> RemoteSessionUpdate | None: ...

    def record(self, recovery_id: str, update: RemoteSessionUpdate) -> str: ...


@dataclass
class InMemoryRecoveryJournal:
    """Small journal double useful for embedding and unit tests.

    Production callers should provide a durable metadata journal.  This class
    never stores messages, tool arguments, or provider response bodies.
    """

    entries: dict[str, RemoteSessionUpdate] = field(default_factory=dict)

    def lookup(self, recovery_id: str) -> RemoteSessionUpdate | None:
        return self.entries.get(recovery_id)

    def record(self, recovery_id: str, update: RemoteSessionUpdate) -> str:
        self.entries.setdefault(recovery_id, update)
        return update.journal_entry_id


def _value(response: Any, name: str) -> Any:
    if isinstance(response, Mapping):
        return response.get(name)
    return getattr(response, name, None)


def _session_generation(provider_session: Mapping[str, Any]) -> int:
    try:
        return int(provider_session.get("session_generation", 0))
    except (TypeError, ValueError):
        return 0


class ResponsesRecoveryPort(RemoteRecoveryPort):
    """Apply provider-native compaction through ``ResponsesManager``."""

    def __init__(
        self,
        manager: ResponsesManager,
        *,
        journal: RecoveryJournal | None = None,
    ) -> None:
        self._manager = manager
        self._journal = journal or InMemoryRecoveryJournal()

    def _update(
        self,
        *,
        generation: int,
        response_id: str | None,
        status: RemoteMutationStatus,
        continuation_allowed: bool,
        journal_entry_id: str,
    ) -> RemoteSessionUpdate:
        return RemoteSessionUpdate(
            session_generation=generation,
            compacted_response_id=response_id,
            remote_mutation_status=status,
            continuation_allowed=continuation_allowed,
            journal_entry_id=journal_entry_id,
        )

    def _record(
        self, recovery_id: str, update: RemoteSessionUpdate
    ) -> RemoteSessionUpdate:
        entry_id = self._journal.record(recovery_id, update)
        if entry_id == update.journal_entry_id:
            return update
        return RemoteSessionUpdate(
            session_generation=update.session_generation,
            compacted_response_id=update.compacted_response_id,
            remote_mutation_status=update.remote_mutation_status,
            continuation_allowed=update.continuation_allowed,
            journal_entry_id=entry_id,
        )

    def apply(
        self,
        plan: RecoveryPlan,
        provider_session: Mapping[str, Any],
        expected_session_generation: int,
    ) -> RemoteSessionUpdate:
        """Compact one remote Responses session with stale/idempotency guards."""
        cached = self._journal.lookup(plan.recovery_id)
        if cached is not None:
            return cached

        current_generation = _session_generation(provider_session)
        journal_entry_id = f"recovery:{plan.recovery_id}"
        if current_generation != int(expected_session_generation):
            return self._record(
                plan.recovery_id,
                self._update(
                    generation=current_generation,
                    response_id=None,
                    status="stale",
                    continuation_allowed=False,
                    journal_entry_id=journal_entry_id,
                ),
            )

        if plan.strategy != "provider_compact":
            return self._record(
                plan.recovery_id,
                self._update(
                    generation=current_generation,
                    response_id=None,
                    status="rejected",
                    continuation_allowed=False,
                    journal_entry_id=journal_entry_id,
                ),
            )

        response_id = str(
            provider_session.get("active_response_id")
            or provider_session.get("response_id")
            or provider_session.get("previous_response_id")
            or ""
        ).strip()
        if not response_id:
            return self._record(
                plan.recovery_id,
                self._update(
                    generation=current_generation,
                    response_id=None,
                    status="rejected",
                    continuation_allowed=False,
                    journal_entry_id=journal_entry_id,
                ),
            )

        try:
            compacted = self._manager.compact(
                response_id,
                input=provider_session.get("input"),
            )
            compacted_id = _value(compacted, "id")
            compacted_id = str(compacted_id).strip() if compacted_id else None
        except Exception:
            return self._record(
                plan.recovery_id,
                self._update(
                    generation=current_generation,
                    response_id=None,
                    status="unknown",
                    continuation_allowed=False,
                    journal_entry_id=journal_entry_id,
                ),
            )

        update = self._update(
            generation=current_generation + 1,
            response_id=compacted_id,
            status="applied",
            continuation_allowed=bool(compacted_id),
            journal_entry_id=journal_entry_id,
        )
        return self._record(plan.recovery_id, update)


__all__ = [
    "InMemoryRecoveryJournal",
    "RecoveryJournal",
    "ResponsesRecoveryPort",
]

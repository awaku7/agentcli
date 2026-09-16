"""Provider-neutral recovery planning for failed LLM context requests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Protocol

from .round_contracts import ContextPlan

RecoveryClassification = Literal[
    "context_overflow",
    "stale_continuation",
    "unsupported_feature",
    "other",
]
RecoveryStrategy = Literal[
    "no_op",
    "provider_compact",
    "client_projection",
    "bounded_rollback",
]
RemoteMutationStatus = Literal[
    "not_attempted",
    "applied",
    "rejected",
    "stale",
    "unknown",
]


@dataclass(frozen=True)
class RecoveryPlan:
    """A replay-safe decision; it does not itself mutate local or remote state."""

    recovery_id: str
    plan_id: str
    projection_id: str | None
    classification: RecoveryClassification
    strategy: RecoveryStrategy
    omitted_message_indexes: tuple[int, ...] = ()
    omitted_message_ids: tuple[str, ...] = ()
    local_history_mutation: bool = False
    remote_session_mutation: bool = False
    projection_mutation: bool = False
    attempt_id: str = ""
    input_fingerprint: str = ""


@dataclass(frozen=True)
class LocalRecoveryResult:
    """Projection inputs produced without changing the persistent history."""

    source_plan_id: str
    messages: tuple[Mapping[str, Any], ...]
    omitted_message_indexes: tuple[int, ...]
    recovery_id: str
    omitted_message_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RemoteSessionUpdate:
    """Result returned by a provider-owned RemoteRecoveryPort operation."""

    session_generation: int
    compacted_response_id: str | None
    remote_mutation_status: RemoteMutationStatus
    continuation_allowed: bool
    journal_entry_id: str


class RemoteRecoveryPort(Protocol):
    """Provider I/O boundary; ContextRecoveryManager never implements this."""

    def apply(
        self,
        plan: RecoveryPlan,
        provider_session: Mapping[str, Any],
        expected_session_generation: int,
    ) -> RemoteSessionUpdate: ...


def _message_size(message: Mapping[str, Any]) -> int:
    try:
        return len(json.dumps(message, ensure_ascii=False, default=str).encode("utf-8"))
    except Exception:
        return 0


def _message_id(message: Mapping[str, Any], index: int) -> str:
    """Return an immutable message identifier for recovery telemetry."""
    for key in ("id", "message_id", "immutable_id"):
        value = message.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"index:{index}"


class ContextRecoveryManager:
    """Classify failures and prepare bounded local recovery without I/O."""

    def __init__(self, *, lookback: int = 10) -> None:
        if lookback < 1:
            raise ValueError("lookback must be positive")
        self._lookback = lookback

    @staticmethod
    def select_bounded_rollback(
        messages: list[Mapping[str, Any]], *, lookback: int = 10
    ) -> tuple[int, int, int] | None:
        """Select the largest recent message without mutating history.

        Returns ``(index, size_bytes, removed_count)`` for the projection
        rollback compatibility path.  The caller remains responsible for
        applying the omission and adding any user-facing notice.
        """
        if not isinstance(messages, list) or not messages or lookback < 1:
            return None
        start = max(0, len(messages) - lookback)
        candidates = [
            (_message_size(message), index)
            for index, message in enumerate(messages[start:], start)
            if isinstance(message, Mapping)
        ]
        if not candidates:
            return None
        size, index = max(candidates)
        return index, size, len(messages) - index

    @staticmethod
    def bounded_rollback_projection(
        messages: list[Mapping[str, Any]], *, lookback: int = 10
    ) -> tuple[tuple[Mapping[str, Any], ...], dict[str, int]] | None:
        """Build a non-mutating legacy rollback projection and metadata."""
        selected = ContextRecoveryManager.select_bounded_rollback(
            messages, lookback=lookback
        )
        if selected is None:
            return None
        index, size, removed = selected
        return tuple(messages[:index]), {
            "index": index,
            "size": size,
            "removed": removed,
        }

    @staticmethod
    def apply_legacy_bounded_rollback(
        messages: list[dict[str, Any]],
        *,
        lookback: int = 10,
        notice_builder: Callable[[int, int, int], Mapping[str, Any]],
    ) -> dict[str, int] | None:
        """Apply the compatibility rollback and return bounded metadata."""
        projection = ContextRecoveryManager.bounded_rollback_projection(
            messages, lookback=lookback
        )
        if projection is None:
            return None
        kept_messages, rollback = projection
        messages[:] = list(kept_messages)
        messages.append(
            dict(notice_builder(lookback, rollback["removed"], rollback["size"]))
        )
        return {
            "index": rollback["index"],
            "size": rollback["size"],
            "removed": rollback["removed"],
        }

    @staticmethod
    def classify(error_text: str) -> RecoveryClassification:
        text = (error_text or "").lower()
        if (
            "input token count exceeds" in text
            or "maximum number of tokens allowed" in text
            or ("context window" in text and ("exceed" in text or "maximum" in text))
        ):
            return "context_overflow"
        if any(
            marker in text
            for marker in (
                "previous_response_id",
                "referenced response not found",
                "response not found or expired",
                "no tool output found",
            )
        ):
            return "stale_continuation"
        if "does not support" in text:
            return "unsupported_feature"
        return "other"

    def plan(
        self,
        *,
        context_plan: ContextPlan,
        projection_id: str | None,
        error_text: str,
        attempt_id: str = "",
        input_fingerprint: str = "",
    ) -> RecoveryPlan:
        classification = self.classify(error_text)
        strategy: RecoveryStrategy = "no_op"
        omitted: tuple[int, ...] = ()
        if classification == "context_overflow" and context_plan.messages:
            start = max(0, len(context_plan.messages) - self._lookback)
            index = max(
                range(start, len(context_plan.messages)),
                key=lambda item: _message_size(context_plan.messages[item]),
            )
            omitted = tuple(range(index, len(context_plan.messages)))
            strategy = "bounded_rollback"
        elif classification == "stale_continuation":
            strategy = "client_projection"
        elif classification == "unsupported_feature":
            strategy = "client_projection"

        omitted_ids = tuple(
            _message_id(context_plan.messages[index], index) for index in omitted
        )
        material = "|".join(
            (
                context_plan.plan_id,
                projection_id or "",
                classification,
                strategy,
                ",".join(str(item) for item in omitted),
                ",".join(omitted_ids),
                attempt_id,
            )
        )
        recovery_id = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return RecoveryPlan(
            recovery_id=recovery_id,
            plan_id=context_plan.plan_id,
            projection_id=projection_id,
            classification=classification,
            strategy=strategy,
            omitted_message_indexes=omitted,
            omitted_message_ids=omitted_ids,
            remote_session_mutation=strategy == "provider_compact",
            projection_mutation=strategy != "no_op",
            attempt_id=attempt_id,
            input_fingerprint=input_fingerprint,
        )

    @staticmethod
    def apply_local(
        plan: RecoveryPlan, context_plan: ContextPlan
    ) -> LocalRecoveryResult:
        if plan.plan_id != context_plan.plan_id:
            raise ValueError("recovery plan does not match the context plan")
        omitted = set(plan.omitted_message_indexes)
        if any(index < 0 or index >= len(context_plan.messages) for index in omitted):
            raise ValueError("recovery plan contains an invalid message index")
        messages = tuple(
            message
            for index, message in enumerate(context_plan.messages)
            if index not in omitted
        )
        return LocalRecoveryResult(
            source_plan_id=context_plan.plan_id,
            messages=messages,
            omitted_message_indexes=plan.omitted_message_indexes,
            recovery_id=plan.recovery_id,
            omitted_message_ids=plan.omitted_message_ids,
        )


__all__ = [
    "ContextRecoveryManager",
    "LocalRecoveryResult",
    "RecoveryClassification",
    "RecoveryPlan",
    "RecoveryStrategy",
    "RemoteRecoveryPort",
    "RemoteMutationStatus",
    "RemoteSessionUpdate",
]

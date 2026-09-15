"""Provider-neutral recovery planning for failed LLM context requests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

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


class ContextRecoveryManager:
    """Classify failures and prepare bounded local recovery without I/O."""

    def __init__(self, *, lookback: int = 10) -> None:
        if lookback < 1:
            raise ValueError("lookback must be positive")
        self._lookback = lookback

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

        material = "|".join(
            (
                context_plan.plan_id,
                projection_id or "",
                classification,
                strategy,
                ",".join(str(item) for item in omitted),
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

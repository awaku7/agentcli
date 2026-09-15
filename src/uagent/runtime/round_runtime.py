"""Runtime guards shared by the incremental LLM round migration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

from .round_contracts import StreamEvent

RetryReason = Literal[
    "stale_continuation",
    "context_overflow",
    "feature_fallback",
    "transport",
    "client_recreate",
]


@dataclass(frozen=True)
class RetryRequest:
    """A requested retry; only RoundAttemptBudget may authorize it."""

    reason: RetryReason
    detail: str = ""


@dataclass
class RoundAttemptBudget:
    """Bound all retry paths for one LLM round in one place."""

    total_limit: int = 1
    reason_limits: Mapping[RetryReason, int] = field(default_factory=dict)
    consumed: list[RetryRequest] = field(default_factory=list, init=False)

    def try_consume(self, request: RetryRequest) -> bool:
        if len(self.consumed) >= self.total_limit:
            return False
        reason_used = sum(item.reason == request.reason for item in self.consumed)
        if reason_used >= self.reason_limits.get(request.reason, self.total_limit):
            return False
        self.consumed.append(request)
        return True

    @property
    def remaining(self) -> int:
        return max(0, self.total_limit - len(self.consumed))


class StreamContractError(ValueError):
    """Raised when an adapter emits an invalid normalized stream sequence."""


_TERMINAL_EVENTS = frozenset(
    {
        "ResponseCompleted",
        "ResponseFailed",
        "ResponseCancelled",
        "ResponseTimedOut",
        "ResponseInterrupted",
    }
)
_EVENT_TYPES = _TERMINAL_EVENTS | {
    "ResponseStarted",
    "TextDelta",
    "TextSnapshot",
    "ReasoningDelta",
    "ToolCallDelta",
    "ToolCallCompleted",
}


class StreamEventValidator:
    """Validate one stream's ordering, mode, tool completion, and terminal event."""

    def __init__(self) -> None:
        self._stream_id: str | None = None
        self._last_sequence: int | None = None
        self._terminal = False
        self._stream_mode: str | None = None
        self._tool_calls: set[str] = set()

    def accept(self, event: StreamEvent) -> None:
        if event.type not in _EVENT_TYPES:
            raise StreamContractError(f"unknown stream event: {event.type}")
        stream_id = event.identifiers.stream_id
        if self._stream_id is None:
            self._stream_id = stream_id
        elif stream_id != self._stream_id:
            raise StreamContractError("validator accepts one stream_id only")
        if self._terminal:
            raise StreamContractError("event received after terminal event")
        if (
            self._last_sequence is not None
            and event.sequence_number <= self._last_sequence
        ):
            raise StreamContractError("stream sequence_number must increase")
        self._last_sequence = event.sequence_number

        if event.type == "ResponseStarted":
            mode = str(event.data.get("stream_mode") or "delta")
            if mode not in {"delta", "snapshot"}:
                raise StreamContractError("unsupported stream mode")
            if self._stream_mode is not None:
                raise StreamContractError("ResponseStarted emitted more than once")
            self._stream_mode = mode
        elif event.type == "TextDelta" and self._stream_mode == "snapshot":
            raise StreamContractError("TextDelta is invalid for a snapshot stream")
        elif event.type == "TextSnapshot" and self._stream_mode != "snapshot":
            raise StreamContractError("TextSnapshot requires a snapshot stream")
        elif event.type == "ToolCallDelta":
            tool_call_id = str(event.data.get("tool_call_id") or "")
            if not tool_call_id:
                raise StreamContractError("ToolCallDelta requires tool_call_id")
            self._tool_calls.add(tool_call_id)
        elif event.type == "ToolCallCompleted":
            tool_call_id = str(event.data.get("tool_call_id") or "")
            if tool_call_id not in self._tool_calls:
                raise StreamContractError("ToolCallCompleted requires a prior delta")
            if not event.data.get("name"):
                raise StreamContractError("ToolCallCompleted requires name")
        elif event.type in _TERMINAL_EVENTS:
            self._terminal = True

    @property
    def terminal(self) -> bool:
        return self._terminal

    def require_terminal(self) -> None:
        if not self._terminal:
            raise StreamContractError("stream ended without a terminal event")


__all__ = [
    "RetryReason",
    "RetryRequest",
    "RoundAttemptBudget",
    "StreamContractError",
    "StreamEventValidator",
]

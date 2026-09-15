"""State machine for Responses API continuation and tool outputs.

This module owns local continuation invariants only.  Provider lifecycle calls
remain in :mod:`responses_manager`; orchestration owns retry execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from .responses_manager import ResponsesCapabilities, get_responses_capabilities
from ..runtime.round_runtime import RetryRequest


ContinuationState = Literal[
    "Fresh",
    "Restored",
    "Continuing",
    "Active",
    "AwaitingToolOutput",
    "Failed",
    "Interrupted",
    "Cancelled",
    "TimedOut",
    "Stale",
]


class ContinuationInvariantError(ValueError):
    """Raised when a Responses continuation invariant is violated."""


class DuplicateToolOutput(ContinuationInvariantError):
    """Raised when a tool output is submitted more than once."""


class UnknownToolOutput(ContinuationInvariantError):
    """Raised when a tool output has no matching pending call."""


@dataclass(frozen=True)
class ToolCallKey:
    """Stable identity for one pending tool call in one response generation."""

    response_id: str
    tool_call_id: str
    session_generation: int


@dataclass
class ResponsesRuntime:
    """Track continuation state without performing provider I/O."""

    provider: str
    model: str = ""
    session_generation: int = 0
    capabilities: ResponsesCapabilities | None = None

    state: ContinuationState = "Fresh"
    previous_response_id: str | None = None
    active_response_id: str | None = None
    last_clear_reason: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.provider = (self.provider or "").strip().lower()
        self.model = self.model or ""
        if self.capabilities is None:
            self.capabilities = get_responses_capabilities(self.provider)
        self._pending: dict[ToolCallKey, Mapping[str, Any]] = {}
        self._accepted_outputs: set[ToolCallKey] = set()

    @property
    def pending_tool_calls(self) -> tuple[ToolCallKey, ...]:
        return tuple(self._pending)

    @property
    def accepted_tool_outputs(self) -> tuple[ToolCallKey, ...]:
        return tuple(self._accepted_outputs)

    def begin_request(self, *, previous_response_id: str | None = None) -> None:
        """Begin a request, optionally continuing the tracked response."""
        if previous_response_id:
            if self._pending:
                raise ContinuationInvariantError(
                    "all pending tool outputs must be accepted before continuation"
                )
            if not self.capabilities.previous_response_id:
                self.clear_continuation("unsupported_continuation")
                raise ContinuationInvariantError(
                    f"provider does not support previous_response_id: {self.provider}"
                )
            if (
                self.previous_response_id
                and previous_response_id != self.previous_response_id
            ):
                self.clear_continuation("continuation_mismatch")
                raise ContinuationInvariantError("previous_response_id mismatch")
            self.previous_response_id = previous_response_id
            self.state = "Continuing"
        elif self.state not in {"Fresh", "Restored", "Stale"}:
            raise ContinuationInvariantError(
                f"cannot begin a fresh request from state {self.state}"
            )
        self.state = "Active"

    def record_response(
        self,
        response_id: str,
        *,
        tool_calls: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] = (),
    ) -> None:
        """Record a response and its pending function calls."""
        response_id = str(response_id or "").strip()
        if not response_id:
            raise ContinuationInvariantError("response_id must not be empty")
        if self.state not in {"Active", "Continuing"}:
            raise ContinuationInvariantError(
                f"cannot record response from state {self.state}"
            )
        self.active_response_id = response_id
        self.previous_response_id = response_id
        self._pending.clear()
        seen: set[str] = set()
        for call in tool_calls:
            call_id = self._tool_call_id(call)
            if not call_id or call_id in seen:
                raise ContinuationInvariantError("tool call IDs must be unique")
            seen.add(call_id)
            key = ToolCallKey(response_id, call_id, self.session_generation)
            self._pending[key] = dict(call)
        self.state = "AwaitingToolOutput" if self._pending else "Fresh"

    def accept_tool_output(
        self,
        response_id: str,
        tool_call_id: str,
        output: Any = None,
        *,
        session_generation: int | None = None,
        failed: bool = False,
    ) -> None:
        """Accept exactly one output for a pending tool call."""
        generation = (
            self.session_generation
            if session_generation is None
            else int(session_generation)
        )
        key = ToolCallKey(str(response_id), str(tool_call_id), generation)
        if key in self._accepted_outputs:
            self._fail("duplicate_tool_output")
            raise DuplicateToolOutput(str(key))
        if key not in self._pending:
            self._fail("unknown_tool_output")
            raise UnknownToolOutput(str(key))
        if failed:
            self._fail("failed_tool_output")
            raise ContinuationInvariantError("failed tool output cannot continue")
        self._pending.pop(key)
        self._accepted_outputs.add(key)
        if not self._pending:
            self.state = "Continuing"

    def request_stale_retry(self, detail: str = "stale continuation") -> RetryRequest:
        """Return a retry request and invalidate the stale continuation."""
        self._clear_ids()
        self.state = "Stale"
        return RetryRequest(reason="stale_continuation", detail=detail)

    def accept_retry(self, request: RetryRequest, *, authorized: bool) -> bool:
        """Apply an orchestrator-approved retry transition."""
        if not authorized:
            self.state = "Failed"
            return False
        if request.reason == "stale_continuation" and self.state == "Stale":
            self.state = "Fresh"
            return True
        if self.state in {"Failed", "Interrupted", "Cancelled", "TimedOut"}:
            self.state = "Fresh"
            return True
        return False

    def restore_continuation(
        self,
        response_id: str,
        *,
        session_generation: int,
        provider: str | None = None,
        model: str | None = None,
        valid: bool = True,
    ) -> bool:
        """Restore a continuation only when provider and generation match."""
        provider_key = (provider or self.provider).strip().lower()
        if (
            not valid
            or provider_key != self.provider
            or (model is not None and model != self.model)
            or not self.capabilities.previous_response_id
        ):
            self.clear_continuation("restore_validation_failed")
            return False
        self.session_generation = int(session_generation)
        self.previous_response_id = str(response_id or "").strip() or None
        if self.previous_response_id is None:
            self.clear_continuation("missing_response_id")
            return False
        self.state = "Restored"
        return True

    def switch_provider(self, provider: str, model: str | None = None) -> None:
        """Clear continuation before changing provider or model."""
        provider_key = (provider or "").strip().lower()
        if provider_key != self.provider or (model is not None and model != self.model):
            self.clear_continuation("provider_switch")
            self.provider = provider_key
            if model is not None:
                self.model = model
            self.capabilities = get_responses_capabilities(self.provider)

    def interrupt(self) -> None:
        self._terminal_clear("Interrupted")

    def cancel(self) -> None:
        self._terminal_clear("Cancelled")

    def timeout(self) -> None:
        self._terminal_clear("TimedOut")

    def clear_continuation(self, reason: str = "clear") -> None:
        """Drop response IDs and pending tool outputs without touching history."""
        self._clear_ids()
        self.state = "Fresh"
        self.last_clear_reason = reason

    def snapshot(self) -> dict[str, Any]:
        """Return safe state metadata suitable for a session journal."""
        return {
            "provider": self.provider,
            "model": self.model,
            "session_generation": self.session_generation,
            "state": self.state,
            "previous_response_id": self.previous_response_id,
            "active_response_id": self.active_response_id,
            "pending_tool_calls": [
                {
                    "response_id": key.response_id,
                    "tool_call_id": key.tool_call_id,
                    "session_generation": key.session_generation,
                }
                for key in self._pending
            ],
        }

    def _tool_call_id(self, call: Mapping[str, Any]) -> str:
        return str(call.get("tool_call_id") or call.get("id") or "").strip()

    def _clear_ids(self) -> None:
        self.previous_response_id = None
        self.active_response_id = None
        self._pending.clear()
        self._accepted_outputs.clear()

    def _fail(self, reason: str) -> None:
        self._clear_ids()
        self.state = "Failed"
        self.last_clear_reason = reason

    def _terminal_clear(self, state: ContinuationState) -> None:
        self._clear_ids()
        self.state = state


__all__ = [
    "ContinuationInvariantError",
    "ContinuationState",
    "DuplicateToolOutput",
    "ResponsesRuntime",
    "ToolCallKey",
    "UnknownToolOutput",
]

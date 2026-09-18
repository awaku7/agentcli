"""Pure mutation decisions for Responses command operations."""

from __future__ import annotations

from dataclasses import dataclass

from .responses_command_state import ResponsesCommandState


@dataclass(frozen=True)
class ResponsesMutationPlan:
    """Decision returned after a remote Responses mutation succeeds."""

    operation: str
    response_id: str
    clear_continuation: bool


class ResponsesCommandMutationService:
    """Decide which local continuation state a command must invalidate."""

    def __init__(self, state: ResponsesCommandState) -> None:
        self._state = state

    def after_cancel(self, response_id: str, *, explicit_id: bool) -> ResponsesMutationPlan:
        # Preserve the existing explicit-cancel contract: the command is
        # authoritative and clears the local continuation after success.
        return ResponsesMutationPlan(
            operation="cancel",
            response_id=response_id,
            clear_continuation=bool(explicit_id or self._state.is_current(response_id)),
        )

    def after_delete(self, response_id: str) -> ResponsesMutationPlan:
        return ResponsesMutationPlan(
            operation="delete",
            response_id=response_id,
            clear_continuation=self._state.is_current(response_id),
        )


__all__ = ["ResponsesCommandMutationService", "ResponsesMutationPlan"]

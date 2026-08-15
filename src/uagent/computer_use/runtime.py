"""Provider-independent Computer Runtime execution boundary."""

from __future__ import annotations

from typing import Protocol

from .actions import ComputerAction
from .policy import ComputerUsePolicy
from .results import ComputerActionResult, Screenshot


class ComputerRuntime(Protocol):
    """Minimal Runtime interface used by the action executor."""

    def execute(self, action: ComputerAction) -> ComputerActionResult: ...

    def screenshot(self) -> Screenshot: ...


def execute_action(
    action: ComputerAction,
    *,
    policy: ComputerUsePolicy,
    runtime: ComputerRuntime,
    domain: str | None = None,
) -> ComputerActionResult:
    """Run one action after the mandatory pre-execution policy check."""
    decision = policy.check(action, domain=domain)
    if not decision.allowed:
        return ComputerActionResult(
            action_id=action.action_id,
            success=False,
            error=decision.reason,
        )

    try:
        # The Runtime is deliberately called only after the policy gate.
        result = runtime.execute(action)
    except Exception as exc:  # Runtime errors become provider-safe results.
        return ComputerActionResult(
            action_id=action.action_id,
            success=False,
            error=str(exc),
        )

    if result.action_id != action.action_id:
        return ComputerActionResult(
            action_id=action.action_id,
            success=False,
            error="runtime returned a mismatched action_id",
        )
    return result

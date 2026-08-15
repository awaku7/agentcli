"""Provider-independent Computer Runtime execution boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .actions import ComputerAction
from .audit import make_audit_event
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
    confirm: Callable[[ComputerAction], bool] | None = None,
    audit: Any | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> ComputerActionResult:
    """Run one action after the mandatory pre-execution policy check."""
    decision = policy.check(action, domain=domain)
    if audit is not None:
        audit.record(
            make_audit_event(
                phase="before_execute",
                action=action,
                session_id=session_id,
                turn_id=turn_id,
                success=decision.allowed,
                error=decision.reason or None,
            )
        )
    if decision.requires_confirmation:
        if confirm is None or not confirm(action):
            result = ComputerActionResult(
                action_id=action.action_id,
                success=False,
                error="user confirmation was not granted",
            )
            if audit is not None:
                audit.record(
                    make_audit_event(
                        phase="after_execute",
                        action=action,
                        session_id=session_id,
                        turn_id=turn_id,
                        success=False,
                        error=result.error,
                    )
                )
            return result
    elif not decision.allowed:
        result = ComputerActionResult(
            action_id=action.action_id,
            success=False,
            error=decision.reason,
        )
        if audit is not None:
            audit.record(
                make_audit_event(
                    phase="after_execute",
                    action=action,
                    session_id=session_id,
                    turn_id=turn_id,
                    success=False,
                    error=result.error,
                )
            )
        return result

    try:
        # The Runtime is deliberately called only after the policy gate.
        result = runtime.execute(action)
    except Exception as exc:  # Runtime errors become provider-safe results.
        result = ComputerActionResult(
            action_id=action.action_id,
            success=False,
            error=str(exc),
        )

    if result.action_id != action.action_id:
        result = ComputerActionResult(
            action_id=action.action_id,
            success=False,
            error="runtime returned a mismatched action_id",
        )
    if audit is not None:
        audit.record(
            make_audit_event(
                phase="after_execute",
                action=action,
                session_id=session_id,
                turn_id=turn_id,
                success=result.success,
                error=result.error,
            )
        )
    return result

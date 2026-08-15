"""Deterministic Runtime used by tests and dry-run execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..actions import ComputerAction
from ..results import ComputerActionResult, Screenshot


@dataclass
class MockComputerRuntime:
    """Record actions without touching the host OS."""

    fail_action: str | None = None
    executed: list[ComputerAction] = field(default_factory=list)

    def screenshot(self) -> Screenshot:
        return Screenshot(data=b"mock-screenshot", media_type="image/png")

    def execute(self, action: ComputerAction) -> ComputerActionResult:
        self.executed.append(action)
        if action.action == self.fail_action:
            return ComputerActionResult(
                action_id=action.action_id,
                success=False,
                error=f"mock runtime failure: {action.action}",
            )
        screenshot = self.screenshot() if action.action == "screenshot" else None
        return ComputerActionResult(
            action_id=action.action_id,
            success=True,
            screenshot=screenshot,
        )

"""Desktop Computer Runtime backend boundary."""

from __future__ import annotations

from typing import Any

from ..actions import ComputerAction
from ..results import ComputerActionResult, Screenshot


class DesktopRuntime:
    """Delegate OS-specific input and capture to an injected backend."""

    def __init__(self, backend: Any):
        self.backend = backend

    def screenshot(self) -> Screenshot:
        return Screenshot(data=self.backend.screenshot(), media_type="image/png")

    def execute(self, action: ComputerAction) -> ComputerActionResult:
        try:
            if action.action == "screenshot":
                return ComputerActionResult(
                    action_id=action.action_id,
                    success=True,
                    screenshot=self.screenshot(),
                )
            raw = self.backend.execute(action)
            if isinstance(raw, dict) and raw.get("success") is False:
                return ComputerActionResult(
                    action_id=action.action_id,
                    success=False,
                    error=str(raw.get("error") or "desktop action failed"),
                )
            return ComputerActionResult(action_id=action.action_id, success=True)
        except Exception as exc:
            return ComputerActionResult(
                action_id=action.action_id,
                success=False,
                error=str(exc),
            )

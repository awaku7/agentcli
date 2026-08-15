"""Browser Computer Runtime backed by a Playwright-like page object."""

from __future__ import annotations

from typing import Any

from ..actions import ComputerAction
from ..results import ComputerActionResult, Screenshot


class BrowserRuntime:
    """Translate normalized actions to browser page/mouse/keyboard calls."""

    def __init__(self, page: Any):
        self.page = page

    def screenshot(self) -> Screenshot:
        return Screenshot(data=self.page.screenshot(), media_type="image/png")

    def execute(self, action: ComputerAction) -> ComputerActionResult:
        try:
            if action.action == "screenshot":
                return ComputerActionResult(
                    action_id=action.action_id,
                    success=True,
                    screenshot=self.screenshot(),
                )
            if action.action in {"click", "right_click", "middle_click"}:
                x, y = action.coordinate or (None, None)
                if x is None or y is None:
                    raise ValueError("click requires coordinate")
                button = (
                    action.button
                    or {
                        "click": "left",
                        "right_click": "right",
                        "middle_click": "middle",
                    }[action.action]
                )
                self.page.mouse.click(x, y, button=button)
            elif action.action == "double_click":
                x, y = action.coordinate or (None, None)
                if x is None or y is None:
                    raise ValueError("double_click requires coordinate")
                self.page.mouse.dblclick(x, y)
            elif action.action == "move":
                x, y = action.coordinate or (None, None)
                if x is None or y is None:
                    raise ValueError("move requires coordinate")
                self.page.mouse.move(x, y)
            elif action.action == "type":
                self.page.keyboard.type(action.text or "")
            elif action.action == "keypress":
                self.page.keyboard.press(action.key or "")
            elif action.action == "scroll":
                self.page.mouse.wheel(action.scroll_x or 0, action.scroll_y or 0)
            else:
                raise ValueError(f"browser action is not supported: {action.action}")
        except Exception as exc:
            return ComputerActionResult(
                action_id=action.action_id,
                success=False,
                error=str(exc),
            )
        return ComputerActionResult(action_id=action.action_id, success=True)

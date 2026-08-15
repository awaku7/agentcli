"""Browser Computer Runtime backed by a Playwright-like page object."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..actions import ComputerAction
from ..results import ComputerActionResult, Screenshot


class BrowserRuntime:
    """Translate normalized actions to browser page/mouse/keyboard calls."""

    def __init__(self, page: Any):
        self.page = page

    def screenshot(self) -> Screenshot:
        return Screenshot(data=self.page.screenshot(), media_type="image/png")

    def current_domain(self) -> str | None:
        url = getattr(self.page, "url", "")
        try:
            return urlparse(str(url)).hostname
        except Exception:
            return None

    def _ensure_editable_focus(self) -> None:
        """Recover focus when a native coordinate click hits a wrapper element."""
        active_is_editable = self.page.evaluate("""() => {
                const el = document.activeElement;
                return !!el && (el.matches('textarea, select, [contenteditable="true"]') || (el.matches('input') && !['checkbox', 'radio', 'button', 'submit', 'hidden'].includes((el.type || '').toLowerCase())));
            }""")
        if active_is_editable:
            return
        candidates = self.page.locator(
            'input:not([type=checkbox]):not([type=radio]):visible, textarea:visible, [contenteditable="true"]:visible'
        )
        if candidates.count() == 1:
            candidates.first.focus()

    def execute(self, action: ComputerAction) -> ComputerActionResult:
        try:
            if action.action != "screenshot":
                # Make the managed page active in headed mode before input.
                # Playwright input is page-scoped, but foregrounding prevents
                # the user-visible browser from appearing out of sync.
                bring_to_front = getattr(self.page, "bring_to_front", None)
                if callable(bring_to_front):
                    bring_to_front()
            if action.action == "navigate":
                url = str(action.text or "").strip()
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError("navigate requires an absolute http(s) URL")
                self.page.goto(url, wait_until="domcontentloaded")
                self.page.bring_to_front()
                return ComputerActionResult(
                    action_id=action.action_id,
                    success=True,
                    screenshot=self.screenshot(),
                )
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
                self._ensure_editable_focus()
                text = action.text or ""
                editable = self.page.locator(
                    'input:not([type=checkbox]):not([type=radio]):visible, textarea:visible, [contenteditable="true"]:visible'
                )
                if editable.count() == 1:
                    editable.first.fill(text)
                else:
                    self.page.keyboard.type(text)
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

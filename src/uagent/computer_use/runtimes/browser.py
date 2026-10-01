"""Browser Computer Runtime backed by a Playwright-like page object."""

from __future__ import annotations

import sys
import time
from typing import Any
from urllib.parse import urlparse

from ..actions import ComputerAction
from ..results import ComputerActionResult, Screenshot


class BrowserRuntime:
    """Translate normalized actions to browser page/mouse/keyboard calls."""

    def __init__(self, page: Any):
        self.page = page
        self._last_mouse_position: tuple[int, int] | None = None

    def screenshot(self) -> Screenshot:
        # Bound screenshot capture so a stalled renderer cannot leave the
        # entire LLM round in BUSY indefinitely.
        capture = getattr(self.page, "screenshot", None)
        if not callable(capture):
            raise RuntimeError("browser page does not provide screenshot()")
        try:
            data = capture(timeout=5000)
        except TypeError:
            # Keep compatibility with page-like adapters and test doubles.
            data = capture()
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("browser screenshot() must return bytes")
        return Screenshot(
            data=bytes(data),
            media_type="image/png",
        )

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

    @staticmethod
    def _normalize_key(key: str) -> str:
        aliases = {
            "CTRL": "Control",
            "CONTROL": "Control",
            "CMD": "Meta",
            "COMMAND": "Meta",
            "META": "Meta",
            "OPTION": "Alt",
            "ALT": "Alt",
            "ESC": "Escape",
            "RETURN": "Enter",
            "SPACE": "Space",
            "BACKSPACE": "Backspace",
            "ARROWLEFT": "ArrowLeft",
            "ARROWRIGHT": "ArrowRight",
            "ARROWUP": "ArrowUp",
            "ARROWDOWN": "ArrowDown",
        }
        return aliases.get(key.upper(), key)

    def _with_modifiers(self, keys: tuple[str, ...], callback: Any) -> Any:
        modifiers = [self._normalize_key(key) for key in keys]
        pressed: list[str] = []
        try:
            for key in modifiers:
                self.page.keyboard.down(key)
                pressed.append(key)
            return callback()
        finally:
            for key in reversed(pressed):
                self.page.keyboard.up(key)

    def execute(self, action: ComputerAction) -> ComputerActionResult:
        try:
            if action.action == "navigate":
                from ...runtime.logging_setup import log_event

                log_event("computer.runtime.navigate.start", url=action.text or "")
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
                self.page.goto(
                    # Do not wait for all page resources. Sites such as Google
                    # can keep network activity open indefinitely; the next
                    # Computer Use screenshot observes the rendered state.
                    url,
                    wait_until="commit",
                    timeout=10000,
                )
                log_event("computer.runtime.navigate.goto_done", url=url)
                self.page.bring_to_front()
                current_url = str(getattr(self.page, "url", "") or "")
                current = urlparse(current_url)
                if current.scheme not in {"http", "https"} or not current.netloc:
                    raise RuntimeError(
                        "navigation did not leave about:blank: "
                        f"{current_url or '<empty>'}"
                    )
                if current.hostname != parsed.hostname:
                    raise RuntimeError(
                        "navigation landed on unexpected host: "
                        f"{current.hostname or '<empty>'}"
                    )
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
                if button in {"back", "forward"}:
                    direction = "Left" if button == "back" else "Right"
                    modifier = "Meta" if sys.platform == "darwin" else "Alt"
                    shortcut = f"{modifier}+Arrow{direction}"
                    self._with_modifiers(
                        action.keys, lambda: self.page.keyboard.press(shortcut)
                    )
                else:
                    if button == "wheel":
                        button = "middle"
                    self._with_modifiers(
                        action.keys,
                        lambda: self.page.mouse.click(x, y, button=button),
                    )
                self._last_mouse_position = (x, y)
            elif action.action == "double_click":
                x, y = action.coordinate or (None, None)
                if x is None or y is None:
                    raise ValueError("double_click requires coordinate")
                self._with_modifiers(action.keys, lambda: self.page.mouse.dblclick(x, y))
                self._last_mouse_position = (x, y)
            elif action.action == "triple_click":
                x, y = action.coordinate or (None, None)
                if x is None or y is None:
                    raise ValueError("triple_click requires coordinate")
                self.page.mouse.click(x, y, click_count=3)
                self._last_mouse_position = (x, y)
            elif action.action == "move":
                x, y = action.coordinate or (None, None)
                if x is None or y is None:
                    raise ValueError("move requires coordinate")
                self._with_modifiers(action.keys, lambda: self.page.mouse.move(x, y))
                self._last_mouse_position = (x, y)
            elif action.action == "drag":
                if action.path:
                    points = action.path
                    if len(points) < 2:
                        raise ValueError("drag path requires at least two points")
                elif action.region is not None:
                    x1, y1, x2, y2 = action.region
                    points = ((x1, y1), (x2, y2))
                elif (
                    action.coordinate is not None
                    and self._last_mouse_position is not None
                ):
                    points = (self._last_mouse_position, action.coordinate)
                else:
                    raise ValueError("drag requires a path with at least two points")

                def drag_path() -> None:
                    self.page.mouse.move(*points[0])
                    self.page.mouse.down()
                    try:
                        for point in points[1:]:
                            self.page.mouse.move(*point)
                    finally:
                        self.page.mouse.up()

                self._with_modifiers(action.keys, drag_path)
                self._last_mouse_position = points[-1]
            elif action.action == "type":
                text = action.text or ""
                if action.provider == "openai":
                    # CUA type inserts at the current caret/focus; filling the
                    # only detected input would unexpectedly replace its value.
                    self.page.keyboard.type(text)
                else:
                    self._ensure_editable_focus()
                    editable = self.page.locator(
                        'input:not([type=checkbox]):not([type=radio]):visible, textarea:visible, [contenteditable="true"]:visible'
                    )
                    if editable.count() == 1:
                        editable.first.fill(text)
                    else:
                        self.page.keyboard.type(text)
            elif action.action == "keypress":
                key_sequence = action.keys or ((action.key,) if action.key else ())
                if not key_sequence:
                    raise ValueError("keypress requires at least one key")
                chord = "+".join(self._normalize_key(key) for key in key_sequence)
                self.page.keyboard.press(chord)
            elif action.action == "scroll":
                def scroll_at_pointer() -> None:
                    if action.coordinate is not None:
                        self.page.mouse.move(*action.coordinate)
                    self.page.mouse.wheel(action.scroll_x or 0, action.scroll_y or 0)

                self._with_modifiers(action.keys, scroll_at_pointer)
            elif action.action == "wait":
                try:
                    seconds = max(0.0, min(float(action.text or "1"), 60.0))
                except ValueError as exc:
                    raise ValueError("wait text must be a number of seconds") from exc
                wait_for_timeout = getattr(self.page, "wait_for_timeout", None)
                if callable(wait_for_timeout):
                    wait_for_timeout(int(seconds * 1000))
                else:
                    time.sleep(seconds)
            elif action.action == "zoom":
                direction = (action.text or "in").strip().lower()
                key = (
                    "Control+Minus"
                    if direction in {"out", "-", "minus", "decrease"}
                    else "Control+Equal"
                )
                self.page.keyboard.press(key)
            else:
                raise ValueError(f"browser action is not supported: {action.action}")
        except Exception as exc:
            return ComputerActionResult(
                action_id=action.action_id,
                success=False,
                error=str(exc),
            )
        return ComputerActionResult(action_id=action.action_id, success=True)

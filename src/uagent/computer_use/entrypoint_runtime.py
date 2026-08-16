"""Entrypoint-owned Computer Use Runtime lifecycle helpers."""

from __future__ import annotations

import atexit
import os
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class EntrypointRuntimeManager:
    """Own the available Browser and Desktop runtimes for one process."""

    def __init__(
        self,
        runtime: Any,
        closer: Any | None = None,
        *,
        runtimes: dict[str, Any] | None = None,
    ):
        self.runtime = runtime
        self._closer = closer
        self.runtimes = dict(runtimes or {})
        if runtime is not None and not self.runtimes:
            self.runtimes["default"] = runtime
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if callable(self._closer):
            try:
                self._closer()
            except Exception:
                pass


def create_runtime_from_env() -> EntrypointRuntimeManager | None:
    """Create an opt-in runtime for the CLI process.

    Runtime creation is intentionally disabled unless Computer Use is enabled.
    Browser defaults to a visible Chromium window so the user can observe and
    stop actions. Set ``UAGENT_COMPUTER_HEADLESS=1`` for CI/smoke tests.
    """
    enabled = (os.environ.get("UAGENT_COMPUTER_USE") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None

    # Register both backends. ``manager.runtime`` remains the selected
    # backend for existing callers; ``manager.runtimes`` exposes both.
    environment = os.environ.get("UAGENT_COMPUTER_ENVIRONMENT") or "desktop"
    environment = environment.strip().lower()
    if environment not in {"browser", "desktop"}:
        environment = "desktop"

    browser_manager = _create_browser_runtime()
    desktop_manager = _create_desktop_runtime()
    runtimes = {
        "browser": browser_manager.runtime,
        "desktop": desktop_manager.runtime,
    }

    def close() -> None:
        browser_manager.close()
        desktop_manager.close()

    manager = EntrypointRuntimeManager(runtimes[environment], close, runtimes=runtimes)
    atexit.register(manager.close)
    return manager


def _create_browser_runtime() -> EntrypointRuntimeManager:
    from .runtimes.browser import BrowserRuntime

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Browser Runtime requires playwright") from exc

    playwright = sync_playwright().start()
    headless = (os.environ.get("UAGENT_COMPUTER_HEADLESS", "0").strip().lower()) in {
        "1",
        "true",
        "yes",
        "on",
    }
    browser = playwright.chromium.launch(
        headless=headless,
        env={},
        args=["--disable-extensions", "--disable-file-system"],
    )
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.set_default_timeout(30000)
    # Make the headed browser visible and focused before the first LLM turn.
    try:
        page.bring_to_front()
    except Exception:
        pass

    def close() -> None:
        try:
            context.close()
        finally:
            try:
                browser.close()
            finally:
                playwright.stop()

    return EntrypointRuntimeManager(BrowserRuntime(page), close)


def _create_desktop_runtime() -> EntrypointRuntimeManager:
    from .runtimes.desktop import DesktopRuntime

    try:
        import pyautogui
    except ImportError as exc:
        # Keep Desktop Computer Use consistent with other optional integrations.
        # Installation is controlled by UAGENT_AUTO_INSTALL (allow/prompt/off).
        from .._pip_auto import install_with_status

        if not install_with_status(
            "pyautogui",
            module_name="pyautogui",
            display_name="Desktop Computer Use (pyautogui)",
        ):
            raise RuntimeError(
                "Desktop Runtime requires pyautogui; automatic installation failed"
            ) from exc
        import pyautogui

    class PyAutoGUIBackend:
        @staticmethod
        def _move_cursor(x: int | None, y: int | None) -> None:
            if x is None or y is None:
                raise ValueError("move action requires x and y coordinates")
            before = pyautogui.position()
            logger.info(
                "computer.move request=(%s,%s) before=(%s,%s)", x, y, before.x, before.y
            )
            pyautogui.moveTo(x=int(x), y=int(y), duration=0)
            actual = pyautogui.position()
            logger.info("computer.move result=(%s,%s)", actual.x, actual.y)
            if (int(actual.x), int(actual.y)) != (int(x), int(y)):
                raise RuntimeError(
                    f"cursor position mismatch: requested {(x, y)}, got {(actual.x, actual.y)}"
                )

        def screenshot(self) -> bytes:
            image = pyautogui.screenshot()
            from io import BytesIO

            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        def execute(self, action: Any) -> dict[str, Any]:
            logger.info(
                "computer.execute action=%s coordinate=%s",
                action.action,
                action.coordinate,
            )
            x, y = action.coordinate or (None, None)
            if action.action == "click":
                pyautogui.click(x=x, y=y)
            elif action.action == "middle_click":
                pyautogui.click(x=x, y=y, button="middle")
            elif action.action == "double_click":
                pyautogui.doubleClick(x=x, y=y)
            elif action.action == "triple_click":
                pyautogui.click(x=x, y=y, clicks=3, interval=0.1)
            elif action.action == "right_click":
                pyautogui.rightClick(x=x, y=y)
            elif action.action == "type":
                pyautogui.write(action.text or "")
            elif action.action == "keypress":
                pyautogui.press(action.key or "")
            elif action.action == "move":
                self._move_cursor(x, y)
            elif action.action == "scroll":
                if action.scroll_y:
                    pyautogui.scroll(int(action.scroll_y), x=x, y=y)
                if action.scroll_x:
                    pyautogui.hscroll(int(action.scroll_x), x=x, y=y)
            elif action.action == "drag":
                if action.region is not None:
                    start_x, start_y, end_x, end_y = action.region
                elif x is not None and y is not None:
                    start_x, start_y = pyautogui.position()
                    end_x, end_y = x, y
                else:
                    raise ValueError("drag requires coordinate or region")
                pyautogui.moveTo(start_x, start_y, duration=0)
                pyautogui.dragTo(end_x, end_y, duration=0.2, button="left")
            elif action.action == "wait":
                try:
                    seconds = max(0.0, min(float(action.text or "1"), 60.0))
                except ValueError as exc:
                    raise ValueError("wait text must be a number of seconds") from exc
                time.sleep(seconds)
            elif action.action == "navigate":
                url = (action.text or "").strip()
                if not url:
                    raise ValueError("navigate requires a URL in text")
                pyautogui.hotkey("ctrl", "l")
                pyautogui.write(url)
                pyautogui.press("enter")
            elif action.action == "zoom":
                direction = (action.text or "in").strip().lower()
                if direction in {"out", "-", "minus", "decrease"}:
                    pyautogui.hotkey("ctrl", "-")
                else:
                    pyautogui.hotkey("ctrl", "+")
            else:
                return {
                    "success": False,
                    "error": f"desktop action unsupported: {action.action}",
                }
            return {"success": True}

    return EntrypointRuntimeManager(DesktopRuntime(PyAutoGUIBackend()))

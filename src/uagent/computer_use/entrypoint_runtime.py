"""Entrypoint-owned Computer Use Runtime lifecycle helpers."""

from __future__ import annotations

import atexit
import os
from typing import Any


class EntrypointRuntimeManager:
    """Own a concrete Browser or Desktop Runtime for one process."""

    def __init__(self, runtime: Any, closer: Any | None = None):
        self.runtime = runtime
        self._closer = closer
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
    if enabled in {"", "0", "false", "no", "off"}:
        return None

    environment = (
        os.environ.get("UAGENT_COMPUTER_ENVIRONMENT", "browser").strip().lower()
    )
    if environment == "browser":
        return _create_browser_runtime()
    if environment == "desktop":
        return _create_desktop_runtime()
    raise RuntimeError(f"unsupported Computer Use environment: {environment}")


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
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    initial_url = os.environ.get("UAGENT_COMPUTER_BROWSER_URL", "about:blank")
    page.goto(initial_url)
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

    manager = EntrypointRuntimeManager(BrowserRuntime(page), close)
    atexit.register(manager.close)
    return manager


def _create_desktop_runtime() -> EntrypointRuntimeManager:
    from .runtimes.desktop import DesktopRuntime

    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("Desktop Runtime requires pyautogui") from exc

    class PyAutoGUIBackend:
        def screenshot(self) -> bytes:
            image = pyautogui.screenshot()
            from io import BytesIO

            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        def execute(self, action: Any) -> dict[str, Any]:
            x, y = action.coordinate or (None, None)
            if action.action == "click":
                pyautogui.click(x=x, y=y)
            elif action.action == "double_click":
                pyautogui.doubleClick(x=x, y=y)
            elif action.action == "right_click":
                pyautogui.rightClick(x=x, y=y)
            elif action.action == "type":
                pyautogui.write(action.text or "")
            elif action.action == "keypress":
                pyautogui.press(action.key or "")
            elif action.action == "move":
                pyautogui.moveTo(x=x, y=y)
            else:
                return {
                    "success": False,
                    "error": f"desktop action unsupported: {action.action}",
                }
            return {"success": True}

    return EntrypointRuntimeManager(DesktopRuntime(PyAutoGUIBackend()))

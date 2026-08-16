"""Entrypoint-owned Computer Use Runtime lifecycle helpers."""

from __future__ import annotations

import atexit
import os
import logging
import platform
import shutil
import subprocess
import sys
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


def create_runtime_from_env(
    *, force: bool = False, provider: str = "", environment: str = "desktop"
) -> EntrypointRuntimeManager | None:
    """Create the provider/environment-specific Computer Use runtime."""
    enabled = (os.environ.get("UAGENT_COMPUTER_USE") or "").strip().lower()
    if not force and enabled not in {"1", "true", "yes", "on"}:
        return None

    provider_name = str(provider or "").strip().lower()
    environment_name = str(environment or "desktop").strip().lower()
    use_browser = (
        provider_name
        in {
            "openai",
            "azure",
            "azure-openai",
            "azure_foundry",
            "azure-foundry",
            "gemini",
            "vertexai",
        }
        and environment_name == "browser"
    )

    browser_manager: EntrypointRuntimeManager | None = None
    desktop_manager: EntrypointRuntimeManager | None = None
    if use_browser:
        browser_manager = _create_browser_runtime()
    else:
        try:
            desktop_manager = _create_desktop_runtime()
        except Exception as exc:
            logger.warning("Desktop Computer Use runtime unavailable: %s", exc)

    runtimes: dict[str, Any] = {}
    if browser_manager is not None:
        runtimes["browser"] = browser_manager.runtime
    if desktop_manager is not None:
        runtimes["desktop"] = desktop_manager.runtime
    if not runtimes:
        return None

    def close() -> None:
        if browser_manager is not None:
            browser_manager.close()
        if desktop_manager is not None:
            desktop_manager.close()

    manager = EntrypointRuntimeManager(
        next(iter(runtimes.values())), close, runtimes=runtimes
    )
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
    major_version = str(browser.version or "").split(".", 1)[0] or "120"
    system = platform.system()
    if system == "Windows":
        chrome_platform = "Windows NT 10.0; Win64; x64"
    elif system == "Darwin":
        chrome_platform = "Macintosh; Intel Mac OS X 10_15_7"
    else:
        chrome_platform = "X11; Linux x86_64"
    chrome_user_agent = (
        f"Mozilla/5.0 ({chrome_platform}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36"
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent=chrome_user_agent,
    )
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
        def __init__(self) -> None:
            self._browser_started = False
            self._browser_window: int | None = None

        def _browser_windows(self) -> list[int]:
            if os.name != "nt":
                return []
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            candidates: list[int] = []
            callback_type = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )

            def callback(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value.lower()
                if any(name in title for name in ("chrome", "edge", "firefox")):
                    candidates.append(int(hwnd))
                return True

            user32.EnumWindows(callback_type(callback), 0)
            return candidates

        def _focus_browser_window(self, preferred: int | None = None) -> None:
            if os.name != "nt":
                return
            try:
                import ctypes

                user32 = ctypes.windll.user32
                hwnd = preferred or getattr(self, "_browser_window", None)
                if not hwnd or not user32.IsWindow(hwnd):
                    windows = self._browser_windows()
                    hwnd = windows[-1] if windows else None
                if hwnd:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    self._browser_window = int(hwnd)
                    time.sleep(0.15)
            except Exception:
                pass

        @staticmethod
        def _keypress(key: str) -> None:
            value = str(key or "").strip()
            if "+" not in value:
                pyautogui.press(value)
                return
            aliases = {
                "control": "ctrl",
                "ctl": "ctrl",
                "meta": "win",
                "windows": "win",
                "return": "enter",
            }
            parts = [p.strip().lower() for p in value.split("+") if p.strip()]
            pyautogui.hotkey(*(aliases.get(part, part) for part in parts))

        @staticmethod
        def _set_clipboard_text(text: str) -> None:
            if os.name == "nt":
                import ctypes

                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                opened = False
                for _ in range(20):
                    if user32.OpenClipboard(None):
                        opened = True
                        break
                    time.sleep(0.05)
                if not opened:
                    raise RuntimeError("Windows clipboard is locked")
                handle = None
                try:
                    data = (text + "\0").encode("utf-16-le")
                    size = len(data)
                    handle = kernel32.GlobalAlloc(0x0002, size)
                    if not handle:
                        raise RuntimeError("GlobalAlloc failed for clipboard text")
                    address = kernel32.GlobalLock(handle)
                    if not address:
                        raise RuntimeError("GlobalLock failed for clipboard text")
                    try:
                        ctypes.memmove(address, data, size)
                    finally:
                        kernel32.GlobalUnlock(handle)
                    if not user32.EmptyClipboard():
                        raise RuntimeError("EmptyClipboard failed")
                    if not user32.SetClipboardData(13, handle):
                        raise RuntimeError("SetClipboardData failed")
                    handle = None  # ownership transferred to the clipboard
                finally:
                    if handle:
                        kernel32.GlobalFree(handle)
                    user32.CloseClipboard()
                return

            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
                return

            for command in (
                ["wl-copy"],
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ):
                if shutil.which(command[0]):
                    subprocess.run(command, input=text.encode("utf-8"), check=True)
                    return
            raise RuntimeError("No supported clipboard command is available")

        @staticmethod
        def _type_text(text: str) -> None:
            value = str(text or "")
            if value.isascii():
                pyautogui.write(value)
                return
            # pyautogui.write() cannot emit Unicode reliably.
            PyAutoGUIBackend._set_clipboard_text(value)
            paste_key = "command" if sys.platform == "darwin" else "ctrl"
            pyautogui.hotkey(paste_key, "v")
            time.sleep(0.1)

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
            if action.action != "screenshot":
                self._focus_browser_window()
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
                self._type_text(action.text or "")
            elif action.action == "keypress":
                self._keypress(action.key or "")
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
                if not self._browser_started:
                    before_windows = set(self._browser_windows())
                    if os.name == "nt":
                        os.startfile(url)  # type: ignore[attr-defined]
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", url])
                    else:
                        subprocess.Popen(["xdg-open", url])
                    self._browser_started = True
                    time.sleep(1.5)
                    after_windows = [
                        hwnd
                        for hwnd in self._browser_windows()
                        if hwnd not in before_windows
                    ]
                    self._focus_browser_window(
                        after_windows[-1] if after_windows else None
                    )
                else:
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

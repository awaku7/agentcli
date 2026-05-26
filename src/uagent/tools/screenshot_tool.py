from __future__ import annotations

# tools/screenshot_tool.py
from .i18n_helper import make_tool_translator
from .response_util import make_response

_ = make_tool_translator(__file__)

import datetime
import os
import time
from typing import Any

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow
except ImportError:
    pygetwindow = None

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "screenshot",
        "description": _(
            "tool.description",
            default="Captures a screenshot of the entire desktop or a specific window.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool is used for the following purpose: capture a screenshot of the desktop or a specified window.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "screenshot",
                "screenshot",
                "screen capture",
                "window capture",
                "desktop screenshot",
                "png capture",
            ],
        ),
        "x_search_terms_en": [
            "screenshot",
            "screenshot",
            "screen capture",
            "window capture",
            "desktop screenshot",
            "png capture",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": _(
                        "param.file_path.description",
                        default="Path for the saved file (recommended: .png). Defaults to current directory with a timestamp if omitted.",
                    ),
                },
                "window_title": {
                    "type": "string",
                    "description": _(
                        "param.window_title.description",
                        default="Target window title (partial match). If specified, the window is activated and only that region is captured.",
                    ),
                },
                "delay": {
                    "type": "integer",
                    "description": _(
                        "param.delay.description",
                        default="Wait time before capture in seconds. Default is 1 second.",
                    ),
                },
                "close_window": {
                    "type": "boolean",
                    "description": _(
                        "param.close_window.description",
                        default="Whether to close the window after capture. Only effective if window_title is specified. Default is False.",
                    ),
                },
            },
            "required": [],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    if pyautogui is None:
        return make_response(
            False,
            _(
                "err.pyautogui_missing",
                default="[screenshot error] pyautogui module is not installed.",
            ),
        )

    window_title = str(args.get("window_title") or "").strip()
    if window_title and pygetwindow is None:
        return make_response(
            False,
            _(
                "err.pygetwindow_missing",
                default="[screenshot error] pygetwindow module is not installed (required for window targeting).",
            ),
        )

    file_path = str(args.get("file_path") or "").strip()
    delay = args.get("delay", 1)
    close_window = bool(args.get("close_window", False))

    if not file_path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_window" if window_title else ""
        file_path = os.path.abspath(f"screenshot_{ts}{suffix}.png")

    try:
        region = None
        target_win = None

        if window_title:
            windows = pygetwindow.getWindowsWithTitle(window_title)
            if not windows:
                return make_response(
                    False,
                    _(
                        "err.window_not_found",
                        default="[screenshot error] No window found matching title: '{title}'",
                    ).format(title=window_title),
                )

            target_win = windows[0]

            try:
                if target_win.isMinimized:
                    target_win.restore()
                target_win.activate()
            except Exception:
                pass

            time.sleep(delay)
            region = (
                target_win.left,
                target_win.top,
                target_win.width,
                target_win.height,
            )

        else:
            time.sleep(delay)

        pyautogui.screenshot(file_path, region=region)

        # Notify user (beep)
        print("\a", end="", flush=True)

        msg = _("out.ok", default="[screenshot] Successfully saved to {path}").format(
            path=file_path
        )

        if window_title and target_win and close_window:
            try:
                target_win.close()
                msg = _(
                    "out.ok_closed",
                    default="[screenshot] Successfully saved to {path} and closed the window.",
                ).format(path=file_path)
            except Exception as e:
                msg = _(
                    "err.close_fail",
                    default="[screenshot] Successfully saved to {path} but failed to close window: {err}",
                ).format(path=file_path, err=e)

        data: dict[str, Any] = {
            "saved_path": file_path,
            "saved_files": [file_path],
            "attachments": [
                {
                    "type": "image",
                    "mime": "image/png",
                    "name": os.path.basename(file_path),
                    "path": file_path,
                    "saved_path": file_path,
                }
            ],
            "next_action": {
                "type": "user_message",
                "content": _(
                    "next_action.analyze_screenshot",
                    default="Please analyze this screenshot.",
                ),
            },
        }
        if window_title:
            data["window_title"] = window_title
        if region is not None:
            data["region"] = {
                "left": region[0],
                "top": region[1],
                "width": region[2],
                "height": region[3],
            }
        data["delay"] = delay
        data["close_window"] = close_window

        return make_response(True, msg, data=data)

    except Exception as e:
        return make_response(
            False,
            _(
                "err.capture_fail",
                default="[screenshot error] Failed to capture screenshot: {err}",
            ).format(err=e),
        )

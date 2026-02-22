# tools/screenshot_tool.py
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

import os
import datetime
import time
from typing import Any, Dict

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow
except ImportError:
    pygetwindow = None

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "screenshot",
        "description": "デスクトップ画面、または指定したタイトルのウィンドウのスクリーンショットを撮影します。",
        "system_prompt": """このツールは次の目的で使われます: デスクトップ画面、または指定したタイトルのウィンドウのスクリーンショットを撮影します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "保存先のファイルパス（.png推奨）。指定がない場合はカレントディレクトリにタイムスタンプ付きで保存します。",
                },
                "window_title": {
                    "type": "string",
                    "description": "撮影対象のウィンドウタイトル（部分一致）。指定した場合、そのウィンドウを探してアクティブにし、その領域だけを撮影します。",
                },
                "delay": {
                    "type": "integer",
                    "description": "撮影前の待機時間（秒）。デフォルトは1秒（ウィンドウ切り替え用）。",
                },
                "close_window": {
                    "type": "boolean",
                    "description": "撮影後にそのウィンドウを閉じるかどうか。window_title指定時のみ有効。デフォルトはFalse。",
                },
            },
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    if pyautogui is None:
        return "[screenshot error] pyautogui module is not installed."

    window_title = args.get("window_title")
    if window_title and pygetwindow is None:
        return "[screenshot error] pygetwindow module is not installed (required for window targeting)."

    file_path = args.get("file_path", "").strip()
    delay = args.get("delay", 1)
    close_window = args.get("close_window", False)

    if not file_path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_window" if window_title else ""
        file_path = os.path.abspath(f"screenshot_{ts}{suffix}.png")

    try:
        region = None
        target_win = None

        # ウィンドウ指定がある場合
        if window_title:
            windows = pygetwindow.getWindowsWithTitle(window_title)
            if not windows:
                return f"[screenshot error] No window found matching title: '{window_title}'"

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

        # 撮影
        pyautogui.screenshot(file_path, region=region)

        # ユーザー通知
        print("\a", end="", flush=True)

        msg = f"[screenshot] Successfully saved to {file_path}"

        # 閉じる処理
        if window_title and target_win and close_window:
            try:
                target_win.close()
                msg += " and closed the window."
            except Exception as e:
                msg += f" but failed to close window: {e}"

        return msg

    except Exception as e:
        return f"[screenshot error] Failed to capture screenshot: {e}"

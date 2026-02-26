from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict
import sys
import json

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_windows_titles",
        "description": _(
            "tool.description",
            default=(
                "Enumerate top-level window titles on Windows and return structured JSON. "
                "Parameters: 'all' (include non-visible), 'pid' (include PID), 'class' (include window class name)."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool enumerates top-level window titles on Windows and returns structured JSON. "
                "It is Windows-only."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": _(
                        "param.all.description",
                        default="Include non-visible windows",
                    ),
                },
                "pid": {
                    "type": "boolean",
                    "description": _(
                        "param.pid.description",
                        default="Include PID in output",
                    ),
                },
                "class": {
                    "type": "boolean",
                    "description": _(
                        "param.class.description",
                        default="Include window class name in output",
                    ),
                },
            },
            "required": [],
        },
    },
}


# This tool is Windows-only
BUSY_LABEL = False


def run_tool(args: Dict[str, Any]) -> str:
    """List top-level windows on Windows.

    args:
      - all: bool (include non-visible windows)
      - pid: bool (include PID)
      - class: bool (include window class name)

    Returns JSON string:
      {"windows": [{"hwnd": int, "title": str, "visible": bool, "class": str (opt), "pid": int (opt)}], "count": int}
    """

    if sys.platform != "win32":
        return json.dumps(
            {"error": "This tool runs on Windows (win32) only."}, ensure_ascii=False
        )

    include_all = bool(args.get("all", False))
    include_pid = bool(args.get("pid", False))
    include_class = bool(args.get("class", False))

    try:
        import ctypes
        import ctypes.wintypes as wintypes
    except Exception as e:
        return json.dumps({"error": f"ctypes import failed: {e}"}, ensure_ascii=False)

    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    GetWindowTextLengthW = user32.GetWindowTextLengthW
    GetWindowTextLengthW.argtypes = [wintypes.HWND]
    GetWindowTextLengthW.restype = ctypes.c_int

    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetWindowTextW.restype = ctypes.c_int

    IsWindowVisible = user32.IsWindowVisible
    IsWindowVisible.argtypes = [wintypes.HWND]
    IsWindowVisible.restype = wintypes.BOOL

    GetClassNameW = user32.GetClassNameW
    GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetClassNameW.restype = ctypes.c_int

    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    GetWindowThreadProcessId.restype = wintypes.DWORD

    windows = []

    @EnumWindowsProc
    def enum_proc(hwnd, lParam):
        try:
            visible = bool(IsWindowVisible(hwnd))
            if (not include_all) and (not visible):
                return True

            length = GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value

            info = {"hwnd": int(hwnd), "title": title, "visible": visible}

            if include_class:
                buf = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, buf, 256)
                info["class"] = buf.value

            if include_pid:
                pid = wintypes.DWORD(0)
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                info["pid"] = int(pid.value)

            windows.append(info)
        except Exception:
            # keep enumerating
            pass
        return True

    user32.EnumWindows(enum_proc, 0)

    return json.dumps({"windows": windows, "count": len(windows)}, ensure_ascii=False)

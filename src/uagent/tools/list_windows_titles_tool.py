from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

from typing import Any, Dict, List, Optional, Tuple
import sys
import json

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_windows_titles",
        "description": "Enumerate top-level window titles on Windows and return structured JSON.\n"
        "Parameters: 'all' (include non-visible), 'pid' (include PID), 'class' (include window class name).",
        "system_prompt": """このツールは次の目的で使われます: Enumerate top-level window titles on Windows and return structured JSON.\n

このツールの system_prompt です。ツールは説明に従って動作します。
- 追加のユーザー入力が必要な場合は必ず human_ask ツールを使用してください。
- 相対日付（今日／今年など）を扱う場合は get_current_time を呼んで現在時刻を参照してください。
- パスワードや API キー等の秘匿情報を長期記憶や共有メモに保存しないでください。
- ファイルやコード出力は原文全体を省略せずに出力すること（ユーザー指示がない場合）。
""",
        "parameters": {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": "Include non-visible windows",
                },
                "pid": {"type": "boolean", "description": "Include PID in output"},
                "class": {
                    "type": "boolean",
                    "description": "Include window class name in output",
                },
            },
            "required": [],
        },
    },
}


# This tool is Windows-only
BUSY_LABEL = False


def run_tool(args: Dict[str, Any]) -> str:
    """
    args:
      - all: bool (include non-visible windows)
      - pid: bool (include PID)
      - class: bool (include window class name)

    Returns a JSON string: {"windows": [ {"hwnd": int, "title": str, "class": str (opt), "pid": int (opt), "visible": bool }, ... ], "count": int}
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

    windows_raw: List[Tuple[int, str, str, bool]] = []  # hwnd, title, class, visible

    @EnumWindowsProc
    def _cb(hwnd, lParam):
        try:
            visible = bool(IsWindowVisible(hwnd))
            if not include_all and not visible:
                return True

            length = GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if not title or title.strip() == "":
                return True

            # class name
            cls_buf = ctypes.create_unicode_buffer(256)
            cname_len = GetClassNameW(hwnd, cls_buf, 256)
            class_name = cls_buf.value if cname_len > 0 else ""

            windows_raw.append((int(hwnd), title, class_name, visible))
        except Exception:
            # ignore windows that error out
            pass
        return True

    try:
        user32.EnumWindows(_cb, 0)
    except Exception as e:
        return json.dumps({"error": f"EnumWindows failed: {e}"}, ensure_ascii=False)

    def get_pid_of_hwnd(hwnd: int) -> Optional[int]:
        pid = wintypes.DWORD()
        try:
            GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0:
                return None
            return int(pid.value)
        except Exception:
            return None

    windows_out: List[Dict[str, Any]] = []
    for hwnd, title, class_name, visible in windows_raw:
        entry: Dict[str, Any] = {"hwnd": hwnd, "title": title, "visible": visible}
        if include_class:
            entry["class"] = class_name
        if include_pid:
            entry["pid"] = get_pid_of_hwnd(hwnd)
        windows_out.append(entry)

    result = {"windows": windows_out, "count": len(windows_out)}
    return json.dumps(result, ensure_ascii=False)

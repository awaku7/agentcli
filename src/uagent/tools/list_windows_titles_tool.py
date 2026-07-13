"""list_windows_titles_tool

Enumerate top-level window titles across Windows, Linux, and macOS.
Platform-specific libraries are auto-installed via pip on first use.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "devel",
    "function": {
        "name": "list_windows_titles",
        "description": _(
            "tool.description",
            default="List top-level window titles. Supports Windows (native), Linux (X11 via ewmh / Hyprland / Sway / KDE / GNOME), and macOS (via Quartz). Required libraries are auto-installed.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "list_windows_titles",
                "list windows titles",
                "window titles",
                "top-level windows",
                "pid",
                "class name",
            ],
        ),
        "x_search_terms_en": [
            "list_windows_titles",
            "list windows titles",
            "window titles",
            "top-level windows",
            "pid",
            "class name",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": _(
                        "param.all.description",
                        default="Include non-visible windows.",
                    ),
                },
                "pid": {
                    "type": "boolean",
                    "description": _(
                        "param.pid.description",
                        default="Include PID in output.",
                    ),
                },
                "class": {
                    "type": "boolean",
                    "description": _(
                        "param.class.description",
                        default="Include class name (Windows) / X11 class (Linux).",
                    ),
                },
            },
            "required": [],
        },
    },
}


BUSY_LABEL = False


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def _list_windows_win32(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict]:
    import ctypes
    import ctypes.wintypes as wintypes

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
            pass
        return True

    user32.EnumWindows(enum_proc, 0)
    return windows


# ---------------------------------------------------------------------------
# Linux compositor helpers
# ---------------------------------------------------------------------------


def _try_ewmh(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict] | None:
    """X11 via EWMH."""
    from .._pip_auto import auto_install

    if not auto_install("ewmh"):
        return None
    try:
        from ewmh import EWMH  # type: ignore[import-untyped]

        ewmh = EWMH()
        windows = []
        for win in ewmh.getClientList():
            try:
                name = ewmh.getWmName(win) or ""
                desktop = ewmh.getWmDesktop(win)
                visible = bool(desktop is not None and desktop >= 0)
                if (not include_all) and (not visible):
                    continue
                info = {"hwnd": int(win), "title": name, "visible": visible}
                if include_pid:
                    try:
                        pid = ewmh.getWmPid(win)
                        info["pid"] = int(pid) if pid else 0
                    except Exception:
                        pass
                if include_class:
                    try:
                        cls = ewmh.getWmClass(win)
                        info["class"] = str(cls) if cls else ""
                    except Exception:
                        pass
                windows.append(info)
            except Exception:
                continue
        if windows:
            return windows
    except Exception:
        pass
    return None


def _try_hyprctl(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict] | None:
    """Hyprland (Wayland). hyprctl is bundled with the compositor."""
    import shutil
    import subprocess

    if not shutil.which("hyprctl"):
        return None
    try:
        r = subprocess.run(
            ["hyprctl", "clients", "-j"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return None
        clients = json.loads(r.stdout)
        windows = []
        for c in clients:
            try:
                visible = bool(c.get("mapped", False))
                if (not include_all) and (not visible):
                    continue
                info = {
                    "hwnd": c.get("address", 0),
                    "title": c.get("title", "") or "",
                    "visible": visible,
                }
                if include_pid:
                    info["pid"] = int(c.get("pid", 0))
                if include_class:
                    info["class"] = c.get("class", "") or ""
                windows.append(info)
            except Exception:
                continue
        return windows
    except Exception:
        pass
    return None


def _try_swaymsg(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict] | None:
    """Sway (Wayland). swaymsg is bundled with the compositor."""
    import shutil
    import subprocess

    if not shutil.which("swaymsg"):
        return None
    try:
        r = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return None
        tree = json.loads(r.stdout)

        def _walk(node: dict) -> list[dict]:
            results = []
            # i3/sway 互換のノードツリー
            if node.get("type") == "con" and node.get("window") is not None:
                results.append(node)
            for child in node.get("nodes", []):
                results.extend(_walk(child))
            for child in node.get("floating_nodes", []):
                results.extend(_walk(child))
            return results

        windows = []
        for node in _walk(tree):
            try:
                visible = bool(node.get("visible", True))
                if (not include_all) and (not visible):
                    continue
                info = {
                    "hwnd": node.get("id", 0),
                    "title": node.get("name", "") or "",
                    "visible": visible,
                }
                if include_pid:
                    info["pid"] = int(node.get("pid", 0))
                if include_class:
                    info["class"] = (
                        node.get("window_properties", {}).get("class", "") or ""
                    )
                windows.append(info)
            except Exception:
                continue
        return windows
    except Exception:
        pass
    return None


def _try_kde_qdbus(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict] | None:
    """KDE Plasma (Wayland/X11). Uses qdbus to query KWin."""
    import shutil
    import subprocess

    if not shutil.which("qdbus"):
        return None
    try:
        r = subprocess.run(
            ["qdbus", "org.kde.KWin", "/KWin", "org.kde.KWin.windowList"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None

        # qdbus の出力は Qt 形式: "Argument types: (sssi...)\nvalue1\nvalue2..."
        # 典型的には各行が1ウィンドウのデータ (title, pid, ...)
        # 簡易パース: 空行/コメント行をスキップ
        windows = []
        lines = [
            line.strip()
            for line in r.stdout.splitlines()
            if line.strip() and not line.startswith("Argument")
        ]
        # windowList は QVariantList で返り、qdbus は1行1ウィンドウで表示
        for line in lines:
            try:
                parts = line.split(",")
                title = parts[0] if len(parts) > 0 else ""
                pid_str = parts[-1] if len(parts) > 1 else ""
                visible = True  # KDE windowList は可視ウィンドウのみ
                if (not include_all) and (not visible):
                    continue
                info = {
                    "hwnd": hash(title + pid_str),
                    "title": title,
                    "visible": visible,
                }
                if include_pid and pid_str.isdigit():
                    info["pid"] = int(pid_str)
                if include_class:
                    info["class"] = ""
                windows.append(info)
            except Exception:
                continue
        if windows:
            return windows
    except Exception:
        pass
    return None


def _try_gnome_gdbus(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict] | None:
    """GNOME (Wayland/X11). Uses gdbus to query Mutter via Shell.Eval."""
    import shutil
    import subprocess

    if not shutil.which("gdbus"):
        return None
    try:
        js_code = (
            "global.get_window_actors().map(a => ({"
            "title: a.meta_window.title, "
            "pid: a.meta_window.get_pid(), "
            "id: a.meta_window.get_id()"
            "}))"
        )
        r = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Shell",
                "--object-path",
                "/org/gnome/Shell",
                "--method",
                "org.gnome.Shell.Eval",
                js_code,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return None

        # 戻り値: (true, 'JSON文字列', '')
        import ast

        parsed = ast.literal_eval(r.stdout.strip())
        if not isinstance(parsed, tuple) or len(parsed) < 2:
            return None
        success = parsed[0]
        if not success:
            return None
        data = json.loads(parsed[1])
        windows = []
        for item in data:
            try:
                title = item.get("title", "") or ""
                pid = item.get("pid", 0)
                wid = item.get("id", 0)
                visible = bool(title)  # タイトルがあれば可視とみなす
                if (not include_all) and (not visible):
                    continue
                info = {"hwnd": int(wid), "title": title, "visible": visible}
                if include_pid:
                    info["pid"] = int(pid)
                if include_class:
                    info["class"] = ""
                windows.append(info)
            except Exception:
                continue
        return windows
    except Exception:
        pass
    return None


def _list_windows_linux(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict]:
    for attempt in (
        _try_ewmh,  # 1) X11
        _try_hyprctl,  # 2) Hyprland (Wayland)
        _try_swaymsg,  # 3) Sway (Wayland)
        _try_kde_qdbus,  # 4) KDE (Wayland/X11)
        _try_gnome_gdbus,  # 5) GNOME (Wayland/X11)
    ):
        result = attempt(include_all, include_pid, include_class)
        if result is not None:
            return result
    return []


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def _list_windows_macos(
    include_all: bool, include_pid: bool, include_class: bool
) -> list[dict]:
    from .._pip_auto import auto_install

    if not auto_install("pyobjc", "Quartz"):
        raise RuntimeError("Failed to install 'pyobjc' (required on macOS).")

    from Quartz import (  # type: ignore[import-untyped]
        CGWindowListCopyWindowInfo,
        kCGNullWindowID,
        kCGWindowListExcludeDesktopElements,
        kCGWindowListOptionOnScreenOnly,
        kCGWindowListOptionAll,
    )

    option = kCGWindowListOptionAll if include_all else kCGWindowListOptionOnScreenOnly
    option |= kCGWindowListExcludeDesktopElements
    window_list = CGWindowListCopyWindowInfo(option, kCGNullWindowID)

    windows = []
    for win in window_list:
        try:
            title = win.get("kCGWindowName", "") or ""
            wid = win.get("kCGWindowNumber", 0)
            layer = win.get("kCGWindowLayer", 0)
            pid = win.get("kCGWindowOwnerPID", 0)
            bounds = win.get("kCGWindowBounds", {})
            w = int(bounds.get("Width", 0)) if bounds else 0
            h = int(bounds.get("Height", 0)) if bounds else 0

            visible = layer == 0 and w > 0 and h > 0
            if (not include_all) and (not visible):
                continue

            info = {"hwnd": int(wid), "title": title, "visible": visible}
            if include_pid:
                info["pid"] = int(pid)
            if include_class:
                info["class"] = ""
            windows.append(info)
        except Exception:
            continue
    return windows


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_tool(args: dict[str, Any]) -> str:
    include_all = bool(args.get("all", False))
    include_pid = bool(args.get("pid", False))
    include_class = bool(args.get("class", False))

    try:
        if sys.platform == "win32":
            windows = _list_windows_win32(include_all, include_pid, include_class)
        elif sys.platform.startswith("linux"):
            windows = _list_windows_linux(include_all, include_pid, include_class)
        elif sys.platform == "darwin":
            windows = _list_windows_macos(include_all, include_pid, include_class)
        else:
            return json.dumps(
                {"error": f"Unsupported platform: {sys.platform}"},
                ensure_ascii=False,
            )
        return json.dumps(
            {"windows": windows, "count": len(windows)}, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)

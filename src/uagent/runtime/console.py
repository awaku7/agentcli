"""Console output helpers shared by CLI, GUI, and Web adapters."""

from __future__ import annotations

import os
import sys

_COLOR_CODES = {
    "black": (30, 0),
    "red": (31, 4),
    "green": (32, 2),
    "yellow": (33, 6),
    "blue": (34, 1),
    "magenta": (35, 5),
    "cyan": (36, 3),
    "white": (37, 7),
}


def _status_color(label: str, busy: bool) -> tuple[int, int]:
    normalized = (label or "").strip().lower()
    if normalized.startswith("sub-agent:"):
        key = "UAGENT_STATUS_COLOR_SUB_AGENT"
        default = "magenta"
    elif normalized.startswith("tool:"):
        key = "UAGENT_STATUS_COLOR_TOOL"
        default = "cyan"
    elif busy:
        key = "UAGENT_STATUS_COLOR_BUSY"
        default = "yellow"
    else:
        key = "UAGENT_STATUS_COLOR_IDLE"
        default = "green"
    value = (
        (os.environ.get(key) or os.environ.get("UAGENT_STATUS_COLOR") or default)
        .strip()
        .lower()
    )
    return _COLOR_CODES.get(value, _COLOR_CODES[default])


def write_status_line(
    text: str, *, busy: bool, use_color: bool, label: str = ""
) -> None:
    """Write one status line without leaking ANSI on Windows consoles."""
    nl = (chr(13) + chr(10)) if os.name == "nt" else chr(10)
    if not use_color:
        sys.stderr.write(text + nl)
        sys.stderr.flush()
        return
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(wintypes.DWORD(-12).value)
            invalid = wintypes.HANDLE(-1).value
            if handle and handle != invalid:

                class COORD(ctypes.Structure):
                    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

                class SMALL_RECT(ctypes.Structure):
                    _fields_ = [
                        (name, wintypes.SHORT)
                        for name in ("Left", "Top", "Right", "Bottom")
                    ]

                class CSBI(ctypes.Structure):
                    _fields_ = [
                        ("dwSize", COORD),
                        ("dwCursorPosition", COORD),
                        ("wAttributes", wintypes.WORD),
                        ("srWindow", SMALL_RECT),
                        ("dwMaximumWindowSize", COORD),
                    ]

                info = CSBI()
                if kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                    old_attr = int(info.wAttributes)
                    _, windows_color = _status_color(label, busy)
                    kernel32.SetConsoleTextAttribute(
                        handle, (old_attr & 0xF0) | (windows_color | 0x08)
                    )
                    try:
                        data = text + nl
                        written = wintypes.DWORD(0)
                        if not kernel32.WriteConsoleW(
                            handle, data, len(data), ctypes.byref(written), None
                        ):
                            sys.stderr.write(data)
                            sys.stderr.flush()
                    finally:
                        kernel32.SetConsoleTextAttribute(handle, old_attr)
                    return
        except Exception:
            pass
        sys.stderr.write(text + nl)
        sys.stderr.flush()
        return
    esc = chr(27)
    ansi_color, _ = _status_color(label, busy)
    sys.stderr.write(f"{esc}[{ansi_color}m{text}{esc}[0m" + nl)
    sys.stderr.flush()

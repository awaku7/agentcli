"""Console output helpers shared by CLI, GUI, and Web adapters."""

from __future__ import annotations

import os
import sys


def write_status_line(text: str, *, busy: bool, use_color: bool) -> None:
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
                    kernel32.SetConsoleTextAttribute(
                        handle, (old_attr & 0xF0) | (0x0E if busy else 0x0A)
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
    color = (esc + "[33m") if busy else (esc + "[32m")
    sys.stderr.write(f"{color}{text}{esc}[0m" + nl)
    sys.stderr.flush()

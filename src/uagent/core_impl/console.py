"""Console / VT setup helpers (split from core.py)."""

from __future__ import annotations

import os
import sys

from ..env_utils import env_get
from .. import core as _core


def _enable_windows_vt_mode() -> bool:
    """Enable VT processing on stdout/stderr. Return True if stderr supports it."""
    if os.name != "nt":
        return True
    stderr_ok = False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.GetConsoleMode.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.GetConsoleMode.restype = wintypes.BOOL
        kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.SetConsoleMode.restype = wintypes.BOOL

        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        DISABLE_NEWLINE_AUTO_RETURN = 0x0008
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
        # STD_OUTPUT_HANDLE = -11, STD_ERROR_HANDLE = -12
        for std_id in (wintypes.DWORD(-11).value, wintypes.DWORD(-12).value):
            handle = kernel32.GetStdHandle(std_id)
            if not handle or handle == INVALID_HANDLE_VALUE:
                continue
            mode = wintypes.DWORD()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                continue
            new_mode = (
                int(mode.value)
                | ENABLE_VIRTUAL_TERMINAL_PROCESSING
                | DISABLE_NEWLINE_AUTO_RETURN
            )
            if new_mode != int(mode.value):
                if not kernel32.SetConsoleMode(handle, new_mode):
                    continue
            # Confirm VT bit is actually set.
            mode2 = wintypes.DWORD()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode2)):
                continue
            if int(mode2.value) & ENABLE_VIRTUAL_TERMINAL_PROCESSING:
                if std_id == wintypes.DWORD(-12).value:
                    stderr_ok = True
                # stdout success is nice-to-have; status uses stderr.
        if stderr_ok:
            return True
    except Exception:
        pass

    # Fallback: legacy trick that sometimes enables VT on older hosts.
    # Only treat as success when stderr VT bit is actually set afterwards.
    # Returning True without verification leaks raw ESC as "?[32m...?[0m".
    try:
        os.system("")
    except Exception:
        return False

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
        handle = kernel32.GetStdHandle(wintypes.DWORD(-12).value)  # STD_ERROR_HANDLE
        if not handle or handle == INVALID_HANDLE_VALUE:
            return False
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(int(mode.value) & ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        return False


def _get_windows_console_output_encoding() -> str | None:
    if os.name != "nt":
        return None

    try:
        import ctypes

        cp = int(ctypes.windll.kernel32.GetConsoleOutputCP())
        if cp == 65001:
            return "utf-8"
        if cp > 0:
            return f"cp{cp}"
    except Exception:
        pass

    return None


def _looks_like_utf8_terminal() -> bool:
    # Heuristic: ConPTY-based terminals usually set one of these env vars.
    if env_get("WT_SESSION"):
        return True
    if env_get("VSCODE_PID"):
        return True
    term_program = str(env_get("TERM_PROGRAM") or "").lower()
    if term_program in {"vscode", "windows_terminal"}:
        return True
    return False


def _reconfigure_stdio() -> None:
    if os.name != "nt":
        return

    stdout_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    stderr_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())
    if not (stdout_tty or stderr_tty):
        return

    if not _core._FORCE_STDIO_UTF8 and _looks_like_utf8_terminal():
        # Keep Python defaults for ConPTY terminals.
        return

    enc = (
        "utf-8"
        if _core._FORCE_STDIO_UTF8
        else (_get_windows_console_output_encoding() or "cp932")
    )

    # Switch console code page to UTF-8 so ANSI escape sequences (ESC byte 0x1B)
    # are not silently corrupted by cp932 (or other non-UTF-8 code pages).
    # Only do this for classic cmd.exe; ConPTY terminals (WT/VSCode) are skipped above.
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

    try:
        if stdout_tty and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding=enc, errors="replace")
        if stderr_tty and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding=enc, errors="replace")
    except Exception:
        pass

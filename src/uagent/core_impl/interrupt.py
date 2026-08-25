"""Interrupt (F12) monitor helpers (split from core.py)."""

from __future__ import annotations

import sys
import threading

from .. import core as _core


def _check_key_win() -> None:
    """Check dedicated function keys without consuming normal text input."""
    with _core.human_ask_lock:
        if _core.human_ask_active or _core.input_prompt_active or not _core.status_busy:
            return
    try:
        import msvcrt  # type: ignore

        if not msvcrt.kbhit():
            return
        key = msvcrt.getch()
        if key in (b"\x00", b"\xe0") and msvcrt.kbhit():
            scan = msvcrt.getch()
            with _core.interrupt_lock:
                if scan == b"\x86":  # F12
                    _core.interrupt_requested = True
            with _core.auto_pilot_exit_lock:
                if scan in (b"\x85", b"\x86"):  # F11 (legacy) / F12
                    _core.auto_pilot_exit_requested = True
    except Exception:
        pass


def _check_key_posix() -> None:
    """Check F11/F12 terminal escape sequences without consuming text."""
    with _core.human_ask_lock:
        if _core.human_ask_active or _core.input_prompt_active or not _core.status_busy:
            return
    if not sys.stdin.isatty():
        return
    try:
        import select
        import termios
        import tty

        r, _, _ = select.select([sys.stdin], [], [], 0)
        if not r:
            return
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            data = sys.stdin.buffer.read(1)
            if data == b"\x1b":
                for _ in range(4):
                    ready, _, _ = select.select([sys.stdin], [], [], 0.02)
                    if not ready:
                        break
                    data += sys.stdin.buffer.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

        with _core.interrupt_lock:
            if data == b"\x1b[24~":  # F12
                _core.interrupt_requested = True
        with _core.auto_pilot_exit_lock:
            if data in (b"\x1b[23~", b"\x1b[24~"):  # F11 (legacy) / F12
                _core.auto_pilot_exit_requested = True
    except Exception:
        pass


def start_interrupt_monitor() -> None:
    """Start daemon thread that monitors F11/F12 function keys."""
    if _core._interrupt_monitor_thread is not None:
        return

    def _monitor() -> None:
        import os as _os

        while not _core._interrupt_monitor_stop.is_set():
            # Keep monitoring during auto-pilot between rounds as well as
            # during normal BUSY work; otherwise F11 can be lost during the
            # short IDLE gap between the reviewer and the next LLM call.
            if not _core.status_busy and not _core.auto_pilot_active:
                _core._interrupt_monitor_stop.wait(0.1)
                continue

            if not _core._interrupt_enabled:
                _core._interrupt_monitor_stop.wait(0.1)
                continue

            if _os.name == "nt":
                _check_key_win()
            else:
                _check_key_posix()

            _core._interrupt_monitor_stop.wait(0.05)

    _core._interrupt_monitor_thread = threading.Thread(
        target=_monitor, daemon=True, name="uagent-interrupt-monitor"
    )
    _core._interrupt_monitor_thread.start()


def stop_interrupt_monitor() -> None:
    """Stop the interrupt monitor thread."""
    _core._interrupt_monitor_stop.set()
    _core._interrupt_monitor_thread = None

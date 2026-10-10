"""Only F12 may interrupt an active Auto-pilot run."""

from __future__ import annotations

import sys
import threading
from types import SimpleNamespace

from uagent.core_impl import interrupt


def _fake_core():
    return SimpleNamespace(
        human_ask_lock=threading.Lock(),
        human_ask_active=False,
        input_prompt_active=False,
        status_busy=True,
        interrupt_lock=threading.Lock(),
        auto_pilot_exit_lock=threading.Lock(),
        interrupt_requested=False,
        auto_pilot_exit_requested=False,
    )


def test_windows_f12_only(monkeypatch):
    for scan, expected in ((b"\x86", True), (b"\x84", False)):
        core = _fake_core()
        monkeypatch.setattr(interrupt, "_core", core)
        keys = iter((b"\xe0", scan))
        monkeypatch.setitem(
            sys.modules,
            "msvcrt",
            SimpleNamespace(kbhit=lambda: True, getch=lambda: next(keys)),
        )

        interrupt._check_key_win()

        assert core.interrupt_requested is expected
        assert core.auto_pilot_exit_requested is expected


def test_posix_f12_only(monkeypatch):
    class FakeInput:
        def __init__(self, data):
            self.data = iter(data)
            self.remaining = len(data)
            self.buffer = self

        def isatty(self):
            return True

        def fileno(self):
            return 0

        def read(self, count):
            assert count == 1
            self.remaining -= 1
            return bytes([next(self.data)])

    for sequence, expected in ((b"\x1b[24~", True), (b"\x1b[22~", False)):
        core = _fake_core()
        monkeypatch.setattr(interrupt, "_core", core)
        stdin = FakeInput(sequence)
        monkeypatch.setattr(sys, "stdin", stdin)
        monkeypatch.setitem(
            sys.modules,
            "select",
            SimpleNamespace(
                select=lambda readers, _writers, _errors, _timeout: (
                    readers if stdin.remaining else [],
                    [],
                    [],
                )
            ),
        )
        monkeypatch.setitem(
            sys.modules,
            "termios",
            SimpleNamespace(
                TCSADRAIN=1,
                tcgetattr=lambda _fd: [],
                tcsetattr=lambda *_args: None,
            ),
        )
        monkeypatch.setitem(
            sys.modules, "tty", SimpleNamespace(setraw=lambda _fd: None)
        )

        interrupt._check_key_posix()

        assert core.interrupt_requested is expected
        assert core.auto_pilot_exit_requested is expected

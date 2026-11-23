from __future__ import annotations

import select
from contextlib import nullcontext
from queue import Queue

import pytest

from uagent import core
from uagent.cli_impl import stdin_loop


class _FakeStdin:
    """Minimal stdin stand-in that drives the manual prompt path."""

    def __init__(self, lines: list[str], on_readline=None) -> None:
        self._lines = list(lines)
        self._on_readline = on_readline

    @staticmethod
    def isatty() -> bool:
        return True

    def readline(self) -> str:
        if self._on_readline is not None:
            self._on_readline()
        # Stop the loop after the scripted input has been consumed.
        stdin_loop._CLI_SHUTDOWN.set()
        if self._lines:
            return self._lines.pop(0)
        return ""


def _patch_common(monkeypatch, fake_stdin) -> None:
    monkeypatch.setattr(core, "get_prompt", lambda: "User> ")
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(stdin_loop.sys, "stdin", fake_stdin)
    monkeypatch.setattr(stdin_loop, "is_chat_mode", lambda: "off")
    monkeypatch.setattr(stdin_loop, "_append_prompt_history_entry", lambda _text: None)
    monkeypatch.setattr(stdin_loop, "forward_to_mesh", lambda _text: None)
    monkeypatch.setattr(select, "select", lambda r, _w, _x, _t: (r, [], []))


def test_prompt_input_is_not_read_while_status_is_busy(monkeypatch) -> None:
    read_busy_states: list[bool] = []

    def record_read() -> None:
        read_busy_states.append(bool(core.status_busy))

    fake_stdin = _FakeStdin(["hello\n"], on_readline=record_read)
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", True)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)

    def finish_busy_wait(seconds: float) -> None:
        if seconds == 0.05:
            core.status_busy = False

    monkeypatch.setattr(stdin_loop.time, "sleep", finish_busy_wait)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
        event = events.get_nowait()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    # The prompt wait-until-idle path must not read input during a turn.
    assert read_busy_states == [False]
    assert event == {"kind": "user", "text": "hello"}


@pytest.mark.parametrize("command", (":load 0", ":cont"))
def test_load_and_continue_stop_spinner_before_command_output(
    monkeypatch, command: str
) -> None:
    fake_stdin = _FakeStdin([command + "\n"])
    events: Queue = Queue()
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(
        core,
        "set_status",
        lambda busy, label="": calls.append(("status", (busy, label))),
    )
    _patch_common(monkeypatch, fake_stdin)
    monkeypatch.setattr(stdin_loop.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(stdin_loop, "_spinner_paused", lambda: nullcontext())
    monkeypatch.setattr(
        stdin_loop,
        "_stop_spinner_quietly",
        lambda: calls.append(("stop_spinner", None)),
    )

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
        event = events.get_nowait()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert event == {"kind": "command", "text": command}
    assert calls == [
        ("status", (True, "command_pending")),
        ("stop_spinner", None),
    ]

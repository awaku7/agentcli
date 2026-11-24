from __future__ import annotations

import select
from contextlib import nullcontext
from queue import Empty, Queue

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
    # Manual-path tests opt out of the prompt_toolkit session read.
    monkeypatch.setattr(stdin_loop, "_get_prompt_session", lambda: None)


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


@pytest.mark.parametrize("command", (":load 0", ":cont", ":nostr connect"))
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


class _FakePromptApp:
    is_running = False


class _FakePromptSession:
    """PromptSession stand-in returning a scripted result from prompt()."""

    def __init__(self, result) -> None:
        self.app = _FakePromptApp()
        self._result = result
        self.prompt_calls: list = []

    def prompt(self, prompt, **kwargs):
        self.prompt_calls.append((prompt, kwargs))
        if callable(self._result):
            return self._result()
        return self._result


def _patch_toolkit(monkeypatch, session, fake_stdin) -> Queue:
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)
    monkeypatch.setattr(stdin_loop, "_get_prompt_session", lambda: session)
    monkeypatch.setattr(stdin_loop.time, "sleep", lambda _seconds: None)
    return events


def _run_loop() -> None:
    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()


def test_idle_prompt_uses_prompt_toolkit_session(monkeypatch) -> None:
    import prompt_toolkit.patch_stdout

    def _forbidden_patch_stdout():
        raise AssertionError("the idle prompt must not be wrapped in patch_stdout")

    monkeypatch.setattr(
        prompt_toolkit.patch_stdout, "patch_stdout", _forbidden_patch_stdout
    )
    seen: dict = {}

    def _read() -> str:
        seen["toolkit_active"] = getattr(core, "_cli_prompt_toolkit_active", False)
        seen["prompt_app"] = getattr(core, "_cli_prompt_app", None)
        seen["line_open"] = getattr(core, "_prompt_line_open", False)
        stdin_loop._CLI_SHUTDOWN.set()
        return "hello"

    session = _FakePromptSession(_read)
    events = _patch_toolkit(monkeypatch, session, _FakeStdin([]))

    _run_loop()

    assert events.get_nowait() == {"kind": "user", "text": "hello"}
    assert len(session.prompt_calls) == 1
    prompt_arg, kwargs = session.prompt_calls[0]
    assert prompt_arg == "User> "
    assert kwargs.get("key_bindings") is not None
    # While the session prompt is open, the application handle is
    # published so status output can ask it to yield its line.
    assert seen == {
        "toolkit_active": True,
        "prompt_app": session.app,
        "line_open": True,
    }
    assert getattr(core, "_cli_prompt_toolkit_active", False) is False
    assert getattr(core, "_cli_prompt_app", None) is None
    assert getattr(core, "_prompt_line_open", False) is False


def test_idle_prompt_key_bindings_restore_history_and_paste(monkeypatch) -> None:
    session = _FakePromptSession("hello")
    events = _patch_toolkit(monkeypatch, session, _FakeStdin([]))

    def _read_and_stop() -> str:
        stdin_loop._CLI_SHUTDOWN.set()
        return "hello"

    session._result = _read_and_stop
    _run_loop()
    assert events.get_nowait() == {"kind": "user", "text": "hello"}

    _prompt_arg, kwargs = session.prompt_calls[0]
    kb = kwargs["key_bindings"]
    handlers = {tuple(binding.keys): binding.handler for binding in kb.bindings}

    class Buffer:
        complete_state = None
        document = type("Document", (), {"cursor_position_row": 0, "line_count": 1})()
        text = ""
        cursor_position = 0

        def __init__(self) -> None:
            self.calls: list = []
            self.inserted: list = []

        def history_backward(self) -> None:
            self.calls.append("history_backward")

        def history_forward(self) -> None:
            self.calls.append("history_forward")

        def cursor_up(self) -> None:
            self.calls.append("cursor_up")

        def cursor_down(self) -> None:
            self.calls.append("cursor_down")

        def complete_previous(self) -> None:
            self.calls.append("complete_previous")

        def complete_next(self) -> None:
            self.calls.append("complete_next")

        def insert_text(self, data: str) -> None:
            self.inserted.append(data)

    # Up at the first row recalls history instead of moving the cursor.
    buffer = Buffer()
    event = type("Event", (), {"current_buffer": buffer})()
    handlers[("up",)](event)
    assert buffer.calls == ["history_backward"]

    # A bracketed paste is inserted as one edit (newlines normalized),
    # not submitted line by line.
    from prompt_toolkit.keys import Keys

    paste_handler = next(
        binding.handler
        for binding in kb.bindings
        if Keys.BracketedPaste in binding.keys
    )
    buffer = Buffer()
    event = type("Event", (), {"current_buffer": buffer, "data": "line1\r\nline2"})()
    paste_handler(event)
    assert buffer.inserted == ["line1\nline2"]


def test_toolkit_prompt_aborted_when_human_ask_takes_over(monkeypatch) -> None:
    cleared: list = []
    monkeypatch.setattr(
        stdin_loop,
        "_clear_abandoned_prompt",
        lambda prompt="": cleared.append(prompt),
    )

    def _read() -> None:
        with core.human_ask_lock:
            core.human_ask_active = True
        stdin_loop._CLI_SHUTDOWN.set()
        return None

    session = _FakePromptSession(_read)
    events = _patch_toolkit(monkeypatch, session, _FakeStdin([]))

    try:
        _run_loop()
    finally:
        with core.human_ask_lock:
            core.human_ask_active = False

    # The aborted line is dropped, never dispatched as a user message.
    with pytest.raises(Empty):
        events.get_nowait()
    assert cleared == ["User> "]
    assert getattr(core, "_cli_prompt_toolkit_active", False) is False


def test_chat_mode_llm_keeps_manual_prompt(monkeypatch) -> None:
    session = _FakePromptSession("from-session")
    fake_stdin = _FakeStdin(["hello\n"])
    events = _patch_toolkit(monkeypatch, session, fake_stdin)
    monkeypatch.setattr(stdin_loop, "is_chat_mode", lambda: "llm")

    _run_loop()

    assert session.prompt_calls == []
    assert events.get_nowait() == {"kind": "user", "text": "hello"}

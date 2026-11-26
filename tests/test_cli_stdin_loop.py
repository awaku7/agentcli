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
    # Manual-path tests opt out of the prompt_toolkit session read
    # and of the full-screen console view.
    monkeypatch.setattr(stdin_loop, "_get_prompt_session", lambda: None)
    monkeypatch.setattr(stdin_loop, "_get_console_view", lambda: None)


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


class _LifecycleView:
    """Console-view stand-in recording lifecycle calls."""

    eof_sentinel = object()
    reply_cancelled = object()

    def __init__(self) -> None:
        self.running = True
        self.suspend_calls = 0
        self.stop_calls = 0
        self.reply_begins: list = []
        self.reply_ends = 0

    def suspend(self) -> None:
        self.suspend_calls += 1
        self.running = False

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False

    def begin_reply(self, label, *, is_password=False) -> None:
        self.reply_begins.append((label, is_password))

    def wait_reply(self, *, abort):
        return "answer"

    def end_reply(self) -> None:
        self.reply_ends += 1


def test_reply_is_served_by_a_running_view_in_place(monkeypatch, capsys) -> None:
    view = _LifecycleView()
    monkeypatch.setattr(stdin_loop, "_console_view", view)
    fake_stdin = _FakeStdin(["hello\n"])
    events: Queue = Queue()
    ask_queue: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    monkeypatch.setattr(core, "human_ask_message", "Proceed with the thing?")
    _patch_common(monkeypatch, fake_stdin)
    original_queue = core.human_ask_queue
    with core.human_ask_lock:
        core.human_ask_active = True
        core.human_ask_is_password = False
        core.human_ask_queue = ask_queue
        core.human_ask_job_id = None
        core.human_ask_prompt = ""
        core.human_ask_multiline_active = False
    monkeypatch.setattr(
        stdin_loop, "_prompt_toolkit_input", lambda _prompt, **_kw: "legacy"
    )

    def fake_sleep(seconds: float) -> None:
        # The tool side consuming the reply clears the ask flag.
        if seconds == 0.03:
            with core.human_ask_lock:
                core.human_ask_active = False

    monkeypatch.setattr(stdin_loop.time, "sleep", fake_sleep)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()
        with core.human_ask_lock:
            core.human_ask_active = False
            core.human_ask_queue = original_queue

    assert ask_queue.get_nowait() == "answer"
    # The running view answered in place: it was never suspended,
    # the legacy reply prompt never ran, and the question (which
    # lives in the view's document) was not replayed anywhere.
    assert view.reply_begins == [("[REPLY] > ", False)]
    assert view.suspend_calls == 0
    assert "Proceed with the thing?" not in capsys.readouterr().out
    # And the loop's exit stopped the view exactly once.
    assert view.stop_calls == 1
    assert events.get_nowait() == {"kind": "user", "text": "hello"}


def test_password_reply_is_served_by_a_running_view_masked(monkeypatch) -> None:
    view = _LifecycleView()
    monkeypatch.setattr(stdin_loop, "_console_view", view)
    fake_stdin = _FakeStdin(["hello\n"])
    events: Queue = Queue()
    ask_queue: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)
    original_queue = core.human_ask_queue
    with core.human_ask_lock:
        core.human_ask_active = True
        core.human_ask_is_password = True
        core.human_ask_queue = ask_queue
        core.human_ask_job_id = None
        core.human_ask_prompt = ""
        core.human_ask_multiline_active = False

    def fake_sleep(seconds: float) -> None:
        if seconds == 0.03:
            with core.human_ask_lock:
                core.human_ask_active = False

    monkeypatch.setattr(stdin_loop.time, "sleep", fake_sleep)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()
        with core.human_ask_lock:
            core.human_ask_active = False
            core.human_ask_queue = original_queue

    assert ask_queue.get_nowait() == "answer"
    # The view was asked for a masked reply; nothing was suspended
    # and no getpass fallback ran.
    assert view.reply_begins == [("[PASSWORD] > ", True)]
    assert view.suspend_calls == 0
    assert events.get_nowait() == {"kind": "user", "text": "hello"}


def test_chat_mode_suspends_a_running_view(monkeypatch) -> None:
    view = _LifecycleView()
    monkeypatch.setattr(stdin_loop, "_console_view", view)
    fake_stdin = _FakeStdin(["hello\n"])
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)
    monkeypatch.setattr(stdin_loop, "is_chat_mode", lambda: "llm")

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert view.suspend_calls >= 1
    assert events.get_nowait() == {"kind": "user", "text": "hello"}


def test_console_view_f12_interrupts_only_when_busy(monkeypatch) -> None:
    ask_queue: Queue = Queue()
    monkeypatch.setattr(core, "interrupt_requested", False)
    monkeypatch.setattr(core, "auto_pilot_exit_requested", False)
    monkeypatch.setattr(core, "status_busy", False)
    with core.human_ask_lock:
        monkeypatch.setattr(core, "human_ask_active", False)
        monkeypatch.setattr(core, "human_ask_queue", None)

    # Idle: F12 does nothing.
    stdin_loop._console_view_f12()
    assert core.interrupt_requested is False

    # Busy: F12 requests the interrupt, like the legacy monitor.
    monkeypatch.setattr(core, "status_busy", True)
    stdin_loop._console_view_f12()
    assert core.interrupt_requested is True
    assert core.auto_pilot_exit_requested is True

    # Ask pending: F12 cancels the ask and still interrupts.
    monkeypatch.setattr(core, "interrupt_requested", False)
    monkeypatch.setattr(core, "auto_pilot_exit_requested", False)
    with core.human_ask_lock:
        monkeypatch.setattr(core, "human_ask_active", True)
        monkeypatch.setattr(core, "human_ask_queue", ask_queue)
    stdin_loop._console_view_f12()
    assert ask_queue.get_nowait() == "cancel"
    assert core.interrupt_requested is True


def test_view_not_used_when_stdout_is_redirected(monkeypatch) -> None:
    # Regression (PR #483 Codex P2): with stdin interactive but
    # stdout redirected (uag > session.log), the full-screen view
    # still took over — prompt_toolkit fell back to a plain output
    # on the redirected stream and the log received rendered screen
    # updates instead of the ordered output.  The view requires an
    # output TTY as well as an input TTY.
    import io

    fake_stdin = _FakeStdin(["hello\n"])
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)
    monkeypatch.setattr(stdin_loop.sys, "stdout", io.StringIO())
    view_requests: list[bool] = []
    monkeypatch.setattr(
        stdin_loop,
        "_get_console_view",
        lambda: view_requests.append(True) or None,
    )

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert view_requests == []
    assert events.get_nowait() == {"kind": "user", "text": "hello"}


def test_multiline_editor_text_is_echoed_to_the_document(monkeypatch) -> None:
    # Regression (PR #483 Codex P2): with the view active, the "f"
    # editor runs while the view is suspended, and its accepted
    # text was never appended to the document — the resumed
    # transcript showed only "User> f".  The accepted text is now
    # posted as a user segment before dispatch.
    from uagent.runtime import display_channel as dc

    view = _LifecycleView()
    monkeypatch.setattr(stdin_loop, "_console_view", view)
    fake_stdin = _FakeStdin(["f\n"])
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)
    monkeypatch.setattr(stdin_loop, "_can_use_textarea", lambda: True)
    monkeypatch.setattr(stdin_loop, "_multiline_editor", lambda: "multiline\nquestion")

    document = dc.default_document()
    before = len(document.snapshot()[0])

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert events.get_nowait() == {"kind": "user", "text": "multiline\nquestion"}
    new_segments = document.snapshot()[0][before:]
    assert any(
        segment.kind == "user" and "multiline\nquestion" in segment.text
        for segment in new_segments
    )


class _QueuedLineView:
    """View stub handing the loop one line queued during generation."""

    eof_sentinel = object()

    def __init__(self, line: str, token) -> None:
        self.running = True
        self._line: str | None = line
        self.last_pending_token = token
        self.resolved: list = []
        self.suspended = 0
        self.stopped = 0

    def start(self) -> None:
        self.running = True

    def suspend(self) -> None:
        self.suspended += 1
        self.running = False

    def stop(self) -> None:
        self.stopped += 1
        self.running = False

    def set_prompt_text(self, _text: str) -> None:
        pass

    def wait_line(self, *, abort):
        if self._line is not None:
            line, self._line = self._line, None
            return line
        stdin_loop._CLI_SHUTDOWN.set()
        return None

    def resolve_pending(self, token) -> None:
        self.resolved.append(token)


def test_queued_line_marker_resolved_at_dispatch(monkeypatch) -> None:
    # A line the view queued during generation carries a pending
    # token; the loop resolves the marker at the moment the line is
    # dispatched, so the transcript stops calling it "queued" once
    # it has actually been sent.
    import io

    token = object()
    view = _QueuedLineView("queued message", token)
    fake_stdin = _FakeStdin([])
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)

    class _TtyStringIO(io.StringIO):
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(stdin_loop.sys, "stdout", _TtyStringIO())
    monkeypatch.setattr(stdin_loop, "_get_console_view", lambda: view)
    monkeypatch.setattr(stdin_loop, "_console_view", view)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert events.get_nowait() == {"kind": "user", "text": "queued message"}
    assert view.resolved == [token]


class _OvertakeView:
    """Hands out a held line first; a priority line then overtakes."""

    eof_sentinel = object()

    def __init__(self) -> None:
        self.running = True
        self.last_pending_token = None
        self.held_token = object()
        self.calls = 0
        self.front: list = []
        self.requeued: list = []
        self.resolved: list = []
        self._priority: str | None = "urgent message"

    def start(self) -> None:
        self.running = True

    def suspend(self) -> None:
        self.running = False

    def stop(self) -> None:
        self.running = False

    def set_prompt_text(self, _text: str) -> None:
        pass

    def wait_line(self, *, abort):
        self.calls += 1
        if self.calls == 1:
            self.last_pending_token = self.held_token
            return "held message"
        if self.front:
            text, self.last_pending_token = self.front.pop(0)
            return text
        stdin_loop._CLI_SHUTDOWN.set()
        return None

    def take_priority_line(self):
        line, self._priority = self._priority, None
        return line

    def requeue_front(self, text, token=None) -> None:
        self.requeued.append((text, token))
        self.front.append((text, token))

    def resolve_pending(self, token) -> None:
        self.resolved.append(token)


def test_priority_line_overtakes_the_held_line(monkeypatch) -> None:
    # A line read just before a turn started can sit in the loop
    # while the user submits another message and chooses to
    # interrupt for it. The chosen line was explicitly picked to go
    # next, so it dispatches first; the held line returns to the
    # front of the queue and follows with its marker resolved at
    # its own dispatch.
    import io

    view = _OvertakeView()
    fake_stdin = _FakeStdin([])
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)

    class _TtyStringIO(io.StringIO):
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(stdin_loop.sys, "stdout", _TtyStringIO())
    monkeypatch.setattr(stdin_loop, "_get_console_view", lambda: view)
    monkeypatch.setattr(stdin_loop, "_console_view", view)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert events.get_nowait() == {"kind": "user", "text": "urgent message"}
    assert events.get_nowait() == {"kind": "user", "text": "held message"}
    assert view.requeued == [("held message", view.held_token)]
    assert view.resolved == [view.held_token]


class _AskRequeueView:
    """Hands out one queued line; records requeues and resolves."""

    eof_sentinel = object()
    reply_cancelled = object()

    def __init__(self, flip_early: bool) -> None:
        self.running = True
        self.last_pending_token = None
        self.token = object()
        self.calls = 0
        self.flip_early = flip_early
        self.front: list = []
        self.requeued: list = []
        self.resolved: list = []

    def start(self) -> None:
        self.running = True

    def suspend(self) -> None:
        self.running = False

    def stop(self) -> None:
        self.running = False

    def set_prompt_text(self, _text: str) -> None:
        pass

    def wait_line(self, *, abort):
        self.calls += 1
        if self.calls == 1:
            # A turn starts while this read is in flight (the race
            # the busy-at-submit hold exists for); in the early
            # variant its human_ask opens at the same moment.
            core.status_busy = True
            if self.flip_early:
                with core.human_ask_lock:
                    core.human_ask_active = True
            self.last_pending_token = self.token
            return "queued message"
        if self.front:
            text, self.last_pending_token = self.front.pop(0)
            return text
        stdin_loop._CLI_SHUTDOWN.set()
        return None

    def take_priority_line(self):
        return None

    def requeue_front(self, text, token=None) -> None:
        self.requeued.append((text, token))
        self.front.append((text, token))

    def resolve_pending(self, token) -> None:
        self.resolved.append(token)

    # A running view answers an ask in place; the scenario's reply
    # is the same "answer" the legacy prompt stub used to give.
    def begin_reply(self, _label, *, is_password=False) -> None:
        pass

    def wait_reply(self, *, abort):
        return "answer"

    def end_reply(self) -> None:
        pass


def _run_ask_requeue_scenario(monkeypatch, *, flip_early: bool) -> None:
    import io

    view = _AskRequeueView(flip_early)
    fake_stdin = _FakeStdin([])
    events: Queue = Queue()
    ask_queue: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    monkeypatch.setattr(core, "human_ask_message", "Proceed?")
    _patch_common(monkeypatch, fake_stdin)
    original_queue = core.human_ask_queue
    with core.human_ask_lock:
        core.human_ask_active = False
        core.human_ask_is_password = False
        core.human_ask_queue = ask_queue
        core.human_ask_job_id = None
        core.human_ask_prompt = ""
        core.human_ask_multiline_active = False
    monkeypatch.setattr(
        stdin_loop, "_prompt_toolkit_input", lambda _prompt, **_kw: "answer"
    )

    def fake_sleep(seconds: float) -> None:
        if seconds == 0.05 and not flip_early:
            # The running turn opens its question during the hold.
            with core.human_ask_lock:
                core.human_ask_active = True
        if seconds == 0.03:
            # The tool side consuming the reply clears the ask.
            with core.human_ask_lock:
                core.human_ask_active = False
            core.status_busy = False

    monkeypatch.setattr(stdin_loop.time, "sleep", fake_sleep)

    class _TtyStringIO(io.StringIO):
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(stdin_loop.sys, "stdout", _TtyStringIO())
    monkeypatch.setattr(stdin_loop, "_get_console_view", lambda: view)
    monkeypatch.setattr(stdin_loop, "_console_view", view)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()
        with core.human_ask_lock:
            core.human_ask_active = False
            core.human_ask_queue = original_queue

    # The question was answered normally while the queued line
    # waited, and the queued line then dispatched exactly once,
    # its marker resolved only at that dispatch.
    assert ask_queue.get_nowait() == "answer"
    assert events.get_nowait() == {"kind": "user", "text": "queued message"}
    assert events.empty()
    assert view.requeued == [("queued message", view.token)]
    assert view.resolved == [view.token]


class _ResyncView:
    """View stub recording the busy re-alignment at each read."""

    eof_sentinel = object()

    def __init__(self) -> None:
        self.running = True
        self.last_pending_token = None
        self.resync_calls: list = []
        self._line: str | None = "hello"

    def start(self) -> None:
        self.running = True

    def suspend(self) -> None:
        self.running = False

    def stop(self) -> None:
        self.running = False

    def set_prompt_text(self, _text: str) -> None:
        pass

    def resync_busy(self, busy: bool) -> None:
        self.resync_calls.append(busy)

    def wait_line(self, *, abort):
        if self._line is not None:
            line, self._line = self._line, None
            return line
        stdin_loop._CLI_SHUTDOWN.set()
        return None

    def resolve_pending(self, token) -> None:
        pass


def test_view_read_resyncs_the_busy_flag(monkeypatch) -> None:
    # Status updates reach the view only while it is active, so
    # every read first re-aligns its cached busy flag with the
    # core's current state.
    import io

    view = _ResyncView()
    fake_stdin = _FakeStdin([])
    events: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    _patch_common(monkeypatch, fake_stdin)

    class _TtyStringIO(io.StringIO):
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(stdin_loop.sys, "stdout", _TtyStringIO())
    monkeypatch.setattr(stdin_loop, "_get_console_view", lambda: view)
    monkeypatch.setattr(stdin_loop, "_console_view", view)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()

    assert events.get_nowait() == {"kind": "user", "text": "hello"}
    assert view.resync_calls
    assert all(flag is False for flag in view.resync_calls)


class _PriorityAskView:
    """Hands out one interrupt-chosen line; records its requeues."""

    eof_sentinel = object()
    reply_cancelled = object()

    def __init__(self, flip_early: bool) -> None:
        self.running = True
        self.last_pending_token = None
        self.last_line_priority = False
        self.calls = 0
        self.flip_early = flip_early
        self.priority_back: list = []
        self.priority_requeued: list = []
        self.resolved: list = []

    def start(self) -> None:
        self.running = True

    def suspend(self) -> None:
        self.running = False

    def stop(self) -> None:
        self.running = False

    def set_prompt_text(self, _text: str) -> None:
        pass

    def wait_line(self, *, abort):
        self.calls += 1
        if self.calls == 1:
            # A turn starts while this read is in flight; in the
            # early variant its human_ask opens at the same moment.
            core.status_busy = True
            if self.flip_early:
                with core.human_ask_lock:
                    core.human_ask_active = True
            self.last_line_priority = True
            return "chosen message"
        if self.priority_back:
            self.last_line_priority = True
            return self.priority_back.pop(0)
        stdin_loop._CLI_SHUTDOWN.set()
        return None

    def take_priority_line(self):
        return None

    def requeue_priority(self, text) -> None:
        self.priority_requeued.append(text)
        self.priority_back.append(text)

    def requeue_front(self, text, token=None) -> None:
        raise AssertionError("a priority line has no token to requeue with")

    def resolve_pending(self, token) -> None:
        self.resolved.append(token)

    # A running view answers an ask in place; the scenario's reply
    # is the same "answer" the legacy prompt stub used to give.
    def begin_reply(self, _label, *, is_password=False) -> None:
        pass

    def wait_reply(self, *, abort):
        return "answer"

    def end_reply(self) -> None:
        pass


def _run_priority_ask_scenario(monkeypatch, *, flip_early: bool) -> None:
    import io

    view = _PriorityAskView(flip_early)
    fake_stdin = _FakeStdin([])
    events: Queue = Queue()
    ask_queue: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    monkeypatch.setattr(core, "human_ask_message", "Proceed?")
    _patch_common(monkeypatch, fake_stdin)
    original_queue = core.human_ask_queue
    with core.human_ask_lock:
        core.human_ask_active = False
        core.human_ask_is_password = False
        core.human_ask_queue = ask_queue
        core.human_ask_job_id = None
        core.human_ask_prompt = ""
        core.human_ask_multiline_active = False
    monkeypatch.setattr(
        stdin_loop, "_prompt_toolkit_input", lambda _prompt, **_kw: "answer"
    )

    def fake_sleep(seconds: float) -> None:
        if seconds == 0.05 and not flip_early:
            with core.human_ask_lock:
                core.human_ask_active = True
        if seconds == 0.03:
            with core.human_ask_lock:
                core.human_ask_active = False
            core.status_busy = False

    monkeypatch.setattr(stdin_loop.time, "sleep", fake_sleep)

    class _TtyStringIO(io.StringIO):
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(stdin_loop.sys, "stdout", _TtyStringIO())
    monkeypatch.setattr(stdin_loop, "_get_console_view", lambda: view)
    monkeypatch.setattr(stdin_loop, "_console_view", view)

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()
        with core.human_ask_lock:
            core.human_ask_active = False
            core.human_ask_queue = original_queue

    # The question was answered normally while the chosen line
    # waited, and the line then dispatched exactly once — it was
    # preserved by its priority flag, not by a pending token.
    assert ask_queue.get_nowait() == "answer"
    assert events.get_nowait() == {"kind": "user", "text": "chosen message"}
    assert events.empty()
    assert view.priority_requeued == ["chosen message"]
    assert view.resolved == []


def test_chosen_line_survives_an_ask_opening_during_the_hold(monkeypatch) -> None:
    _run_priority_ask_scenario(monkeypatch, flip_early=False)


def test_chosen_line_survives_an_ask_already_open_at_the_check(monkeypatch) -> None:
    _run_priority_ask_scenario(monkeypatch, flip_early=True)


def test_queued_line_survives_an_ask_opening_during_the_hold(monkeypatch) -> None:
    _run_ask_requeue_scenario(monkeypatch, flip_early=False)


def test_queued_line_survives_an_ask_already_open_at_the_check(monkeypatch) -> None:
    _run_ask_requeue_scenario(monkeypatch, flip_early=True)


def test_stdin_eof_releases_a_pending_human_ask(monkeypatch) -> None:
    fake_stdin = _FakeStdin([])
    events: Queue = Queue()
    ask_queue: Queue = Queue()
    monkeypatch.setattr(core, "event_queue", events)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "set_status", lambda _busy, _label="": None)
    monkeypatch.setattr(core, "human_ask_message", "Register this device?")
    _patch_common(monkeypatch, fake_stdin)
    monkeypatch.setattr(
        stdin_loop,
        "_prompt_toolkit_input",
        lambda _prompt, **_kw: (_ for _ in ()).throw(EOFError),
    )
    original_queue = core.human_ask_queue
    with core.human_ask_lock:
        core.human_ask_active = True
        core.human_ask_is_password = False
        core.human_ask_queue = ask_queue
        core.human_ask_job_id = None
        core.human_ask_prompt = ""
        core.human_ask_multiline_active = False

    stdin_loop._CLI_SHUTDOWN.clear()
    try:
        stdin_loop.stdin_loop()
    finally:
        stdin_loop._CLI_SHUTDOWN.clear()
        with core.human_ask_lock:
            core.human_ask_active = False
            core.human_ask_queue = original_queue

    # EOF cancelled the pending ask (None) instead of leaving its
    # waiter blocked until the ask timeout, and exit was requested.
    assert ask_queue.get_nowait() is None
    assert events.get_nowait() == {"kind": "command", "text": ":exit"}

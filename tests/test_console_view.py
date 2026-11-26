"""Tests for the full-screen console view (single-writer stage 2b).

The view runs headlessly here: prompt_toolkit pipe input + dummy
output, projecting a fresh output document per test.  Producer
routing is checked against the channel's document (the pump records
there in every mode) and against a fake view registered as the
active one for the spinner/status setters.
"""

from __future__ import annotations


import time

import pytest

from uagent.cli_impl import console_view
from uagent.cli_impl.console_view import ConsoleView
from uagent.runtime import display_channel as dc


@pytest.fixture(autouse=True)
def _clear_active_view():
    yield
    console_view._set_active(None)


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def _document_text(document) -> str:
    segments, _version, _epoch = document.snapshot()
    return "".join(segment.text for segment in segments)


def test_view_submits_lines_and_projects_document():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert console_view.active_view() is view
            document.append("answer", "assistant text")
            assert _wait_for(lambda: "assistant text" in view._output_text)

            view.set_prompt_text("User> ")
            pipe.send_text("hello view\r")
            line = view.wait_line(abort=lambda: False)
            assert line == "hello view"
            # The submission is recorded in the transcript, with
            # its prompt, like the legacy terminal's scrollback.
            assert _wait_for(
                lambda: any(
                    s.kind == "user" and s.text == "User> hello view\n"
                    for s in document.snapshot()[0]
                )
            )

            view.set_spinner("LLM")
            fragments = view._spinner_fragments()
            assert "LLM" in fragments[0][1]
            view.set_spinner(None)
            assert view._spinner_fragments()[0][1] == ""

            view.set_status("[STATE] BUSY [LLM]", busy=True)
            assert view._status_fragments()[0][1] == "[STATE] BUSY [LLM]"
        finally:
            view.stop()
        assert console_view.active_view() is None


def test_view_ctrl_c_and_ctrl_d_keys():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    seen: list[str] = []
    with create_pipe_input() as pipe:
        view = ConsoleView(
            pt_input=pipe,
            pt_output=DummyOutput(),
            on_ctrl_c=lambda: seen.append("ctrl-c"),
        )
        view.start()
        try:
            pipe.send_text("\x03")
            assert _wait_for(lambda: seen == ["ctrl-c"])
            pipe.send_text("\x04")
            item = view.wait_line(abort=lambda: False)
            assert item is view.eof_sentinel
        finally:
            view.stop()


def test_view_suspend_and_resume_keeps_output():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        document.append("output", "before suspend")
        assert _wait_for(lambda: "before suspend" in view._output_text)
        view.suspend()
        assert not view.running
        assert console_view.active_view() is None
        view.start()
        try:
            assert console_view.active_view() is view
            assert "before suspend" in view._output_text
            pipe.send_text("again\r")
            assert view.wait_line(abort=lambda: False) == "again"
        finally:
            view.stop()


def test_view_colours_reasoning_by_kind(monkeypatch):
    from prompt_toolkit.document import Document
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("UAGENT_NO_COLOR", raising=False)
    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            # The document holds no colour; the kind alone colours.
            document.append("reasoning", "deep thought")
            document.append("answer", "the answer")
            assert _wait_for(lambda: "the answer" in view._output_text)
            segments, _v, _e = document.snapshot()
            assert [(s.kind, s.text) for s in segments] == [
                ("reasoning", "deep thought"),
                ("answer", "the answer"),
            ]
            fragments = view._lexer.lex_document(Document(view._output_text))(0)
            assert ("ansibrightblack", "deep thought") in fragments
            assert ("", "the answer") in fragments
        finally:
            view.stop()


def test_view_kind_colour_respects_no_color(monkeypatch):
    from prompt_toolkit.document import Document
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    monkeypatch.setenv("NO_COLOR", "1")
    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            document.append("reasoning", "deep thought")
            assert _wait_for(lambda: "deep thought" in view._output_text)
            fragments = view._lexer.lex_document(Document(view._output_text))(0)
            assert fragments == [("", "deep thought")]
        finally:
            view.stop()


def test_view_reprojects_after_snapshot_replace():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            document.append("answer", "intro\nsnap v1 line1\nsnap v1 line2")
            assert _wait_for(lambda: "snap v1 line2" in view._output_text)
            document.replace_last_lines(2, "snap v2", kind="answer")
            assert _wait_for(lambda: view._output_text == "intro\nsnap v2")
        finally:
            view.stop()


class _FakeView:
    """Only the spinner/status setters (the pump no longer uses it)."""

    def __init__(self) -> None:
        self.spinner: list[object] = []
        self.status: list[tuple[str, bool]] = []

    def set_spinner(self, label) -> None:
        self.spinner.append(label)

    def set_status(self, text: str, *, busy: bool) -> None:
        self.status.append((text, busy))


def test_pump_records_stream_and_notices_in_document():
    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    channel = dc.DisplayChannel()

    class _Core:
        _stream_line_open = False
        _reasoning_stream_open = False

        def print_stream_delta(self, text: str) -> None:
            raise AssertionError("legacy renderer must not run")

        def print_reasoning_delta(self, text: str) -> None:
            raise AssertionError("legacy renderer must not run")

    dc._render_stream_event(
        _Core(), channel, dc.StreamDelta(text="delta", kind="answer")
    )
    segments, _v, _e = channel.document.snapshot()
    assert [(s.kind, s.text) for s in segments] == [("answer", "delta")]
    assert channel._stream_pending == 0

    dc.render_notice(
        _Core(),
        dc.Notice(text="a notice", source="test"),
        document=channel.document,
    )
    segments, _v, _e = channel.document.snapshot()
    assert segments[-1].kind == "notice"
    assert segments[-1].text == "a notice\n"


def test_pump_reasoning_mirrors_line_state_and_separator():
    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    channel = dc.DisplayChannel()

    class _Core:
        _stream_line_open = False
        _reasoning_stream_open = False

        def print_stream_delta(self, text: str) -> None:
            raise AssertionError("legacy renderer must not run")

        def print_reasoning_delta(self, text: str) -> None:
            raise AssertionError("legacy renderer must not run")

    core = _Core()
    dc._render_stream_event(
        core, channel, dc.StreamDelta(text="thinking", kind="reasoning")
    )
    assert core._reasoning_stream_open is True
    # The answer first closes the open reasoning line in the
    # document, like the legacy print_stream_delta_locked does.
    dc._render_stream_event(core, channel, dc.StreamDelta(text="answer", kind="answer"))
    assert _document_text(channel.document) == "thinking\nanswer"
    segments, _v, _e = channel.document.snapshot()
    assert [s.kind for s in segments] == ["reasoning", "answer"]
    assert core._reasoning_stream_open is False
    assert core._stream_line_open is True


def test_pump_snapshot_replaces_in_document():
    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    channel = dc.DisplayChannel()

    class _Core:
        _stream_line_open = False
        _reasoning_stream_open = False

        def print_stream_delta(self, text: str) -> None:
            raise AssertionError("legacy renderer must not run")

        def print_reasoning_delta(self, text: str) -> None:
            raise AssertionError("legacy renderer must not run")

    channel.document.append("answer", "intro\nsnap v1 line1\nsnap v1 line2")
    esc = "\x1b"
    prefix = f"\r{esc}[1A{esc}[2K{esc}[1B\r{esc}[2K{esc}[1A\r"
    dc._render_stream_event(
        _Core(), channel, dc.StreamDelta(text=prefix + "snap v2", kind="answer")
    )
    assert _document_text(channel.document) == "intro\nsnap v2"


def test_spinner_drives_view_and_posts_done_line(monkeypatch):
    from uagent.runtime import spinner

    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    monkeypatch.setattr(spinner, "spinner_enabled", lambda: True)
    document = dc.default_document()
    before, _v, _e = document.snapshot()
    before_texts = [s.text for s in before]
    spinner.start()
    assert fake.spinner and fake.spinner[-1] is not None
    spinner.stop()
    assert fake.spinner[-1] is None
    after, _v, _e = document.snapshot()
    assert any(
        s.kind == "notice" and "OK done" in s.text and s.text not in before_texts
        for s in after
    )


def test_print_status_line_routes_to_view(monkeypatch):
    from uagent import core

    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    with core.status_lock:
        core.status_busy = True
        core.status_label = "LLM"
    core.print_status_line()
    assert fake.status == [("[STATE] BUSY [LLM]", True)]
    with core.status_lock:
        core.status_busy = False
        core.status_label = ""


def test_stdin_loop_view_ctrl_c_busy_sets_interrupt(monkeypatch):
    from uagent import core
    from uagent.cli_impl import stdin_loop

    with core.status_lock:
        core.status_busy = True
    with core.interrupt_lock:
        core.interrupt_requested = False
    try:
        stdin_loop._console_view_ctrl_c()
        with core.interrupt_lock:
            assert core.interrupt_requested is True
    finally:
        with core.status_lock:
            core.status_busy = False
        with core.interrupt_lock:
            core.interrupt_requested = False


def test_stdin_loop_view_ctrl_c_idle_requests_exit():
    from uagent import core
    from uagent.cli_impl import stdin_loop

    while not core.event_queue.empty():
        core.event_queue.get()
    stdin_loop._console_view_ctrl_c()
    event = core.event_queue.get(timeout=1.0)
    assert event == {"kind": "command", "text": ":exit"}


class _StubView:
    def __init__(self, item) -> None:
        self._item = item
        self.running = False
        self.suspended = False
        self.eof_sentinel = object()

    def start(self) -> None:
        self.running = True

    def suspend(self) -> None:
        self.suspended = True
        self.running = False

    def set_prompt_text(self, text: str) -> None:
        pass

    def wait_line(self, *, abort):
        if isinstance(self._item, BaseException):
            raise self._item
        return self._item


def test_read_line_from_view_returns_submitted_line():
    from uagent.cli_impl import stdin_loop

    view = _StubView("typed line")
    assert stdin_loop._read_line_from_view(view, "prompt> ") == "typed line"  # type: ignore[arg-type]


def test_read_line_from_view_abort_suspends():
    from uagent.cli_impl import stdin_loop

    view = _StubView(None)
    assert stdin_loop._read_line_from_view(view, "prompt> ") is None  # type: ignore[arg-type]
    assert view.suspended


def test_read_line_from_view_eof_raises():
    from uagent.cli_impl import stdin_loop

    view = _StubView(None)
    view._item = view.eof_sentinel
    with pytest.raises(EOFError):
        stdin_loop._read_line_from_view(view, "prompt> ")  # type: ignore[arg-type]
    assert view.suspended


def test_spinner_style_reuses_existing_flag(monkeypatch):
    monkeypatch.delenv("UAGENT_SPINNER_COLOR", raising=False)
    styles = console_view._spinner_style()
    assert styles["spinner"] == "ansiyellow"
    assert styles["spinner.tool"] == "ansicyan"
    assert styles["spinner.subagent"] == "ansimagenta"
    monkeypatch.setenv("UAGENT_SPINNER_COLOR", "red")
    styles = console_view._spinner_style()
    assert styles == {
        "spinner": "ansired",
        "spinner.tool": "ansired",
        "spinner.subagent": "ansired",
    }


def test_status_styles_follow_existing_policy(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("UAGENT_NO_COLOR", raising=False)
    monkeypatch.delenv("UAGENT_STATUS_COLOR", raising=False)
    assert console_view._status_styles() == {
        "status.busy": "ansiyellow",
        "status.idle": "ansigreen",
    }
    monkeypatch.setenv("UAGENT_STATUS_COLOR", "0")
    assert console_view._status_styles() == {
        "status.busy": "",
        "status.idle": "",
    }


def test_view_enabled_env_opt_out(monkeypatch):
    monkeypatch.setenv("UAGENT_CLI_VIEW", "0")
    assert console_view.view_enabled() is False
    monkeypatch.setenv("UAGENT_CLI_VIEW", "1")
    assert console_view.view_enabled() is True


def test_view_captures_stdout_and_stderr_into_document():
    import sys

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    real_stdout, real_stderr = sys.stdout, sys.stderr
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            assert _wait_for(
                lambda: isinstance(sys.stdout, console_view._ViewStreamProxy)
            )
            print("captured stdout line")
            print("captured stderr line", file=sys.stderr)
            sys.stdout.write("partial")
            assert "partial" not in view._output_text
            sys.stdout.write(" line\n")
            assert _wait_for(lambda: "captured stdout line" in view._output_text)
            assert _wait_for(lambda: "captured stderr line" in view._output_text)
            assert _wait_for(lambda: "partial line" in view._output_text)
            assert sys.stdout.isatty() == real_stdout.isatty()
            # The captured kinds are output (stdout) and debug (stderr).
            segments, _v, _e = dc.default_document().snapshot()
            kinds = {s.text.strip(): s.kind for s in segments if s.text.strip()}
            assert kinds.get("captured stdout line") == "output"
            assert kinds.get("captured stderr line") == "debug"
        finally:
            view.stop()
        assert sys.stdout is real_stdout
        assert sys.stderr is real_stderr


def test_stream_proxy_posts_lines_by_kind(monkeypatch):
    import io

    posted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        dc, "post_segment", lambda kind, text: posted.append((kind, text))
    )
    proxy = console_view._ViewStreamProxy(io.StringIO(), "output")
    proxy.write("abc")
    assert posted == []
    proxy.write("def\nnext")
    assert posted == [("output", "abcdef\n")]
    proxy.flush()
    assert posted == [("output", "abcdef\n"), ("output", "next")]
    assert proxy.encoding
    assert proxy.writable()


def test_view_thread_name_and_single_start():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        first_thread = view._thread
        view.start()  # second start is a no-op
        try:
            assert view._thread is first_thread
            assert first_thread is not None and first_thread.is_alive()
            assert first_thread.name == "uagent-console-view"
        finally:
            view.stop()


def test_tool_trace_line_posts_tool_segment(monkeypatch, capsys):
    from uagent.runtime import display_channel
    from uagent.tools import _trace

    document = display_channel.default_document()

    # No view: the line prints as before AND gathers as "tool".
    monkeypatch.setattr(console_view, "_active_view", None)
    _trace._emit_trace_line("[TOOL] trace-marker-legacy")
    assert "[TOOL] trace-marker-legacy" in capsys.readouterr().out
    segments, _, _ = document.snapshot()
    assert any(s.kind == "tool" and "trace-marker-legacy" in s.text for s in segments)

    # With a view active: no raw print; the document still gathers it.
    monkeypatch.setattr(console_view, "_active_view", _FakeView())
    _trace._emit_trace_line("[TOOL] trace-marker-view")
    assert "trace-marker-view" not in capsys.readouterr().out
    segments, _, _ = document.snapshot()
    assert any(s.kind == "tool" and "trace-marker-view" in s.text for s in segments)


def test_view_f12_binding_fires_callback():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    hits: list[bool] = []
    with create_pipe_input() as pipe:
        view = ConsoleView(
            pt_input=pipe,
            pt_output=DummyOutput(),
            on_f12=lambda: hits.append(True),
        )
        view.start()
        try:
            pipe.send_text("\x1b[24~")
            assert _wait_for(lambda: bool(hits))
        finally:
            view.stop()


def test_interrupt_monitor_stays_out_while_view_active(monkeypatch):
    import io
    import select as select_module
    import sys
    import types

    from uagent import core
    from uagent.core_impl import interrupt

    select_calls: list[bool] = []

    def fake_select(r, _w, _x, _t):
        select_calls.append(True)
        return (r, [], [])

    monkeypatch.setattr(select_module, "select", fake_select)
    monkeypatch.setattr(core, "status_busy", True)
    monkeypatch.setattr(core, "input_prompt_active", False)
    monkeypatch.setattr(core, "human_ask_active", False)
    fake_stdin = types.SimpleNamespace(
        isatty=lambda: True,
        fileno=lambda: -1,
        buffer=io.BytesIO(b""),
    )
    monkeypatch.setattr(sys, "stdin", fake_stdin)

    # View active: the monitor must not touch stdin at all.
    monkeypatch.setattr(console_view, "_active_view", object())
    interrupt._check_key_posix()
    assert select_calls == []

    # No view: the monitor proceeds to its read attempt.
    monkeypatch.setattr(console_view, "_active_view", None)
    interrupt._check_key_posix()
    assert select_calls


def test_suspend_during_startup_never_runs_the_app(monkeypatch) -> None:
    import sys
    import threading

    from uagent.runtime.display_channel import OutputDocument

    view = ConsoleView(document=OutputDocument())
    gate = threading.Event()
    ran: list[bool] = []

    class _StubApp:
        def run(self) -> None:
            ran.append(True)

        def exit(self) -> None:
            pass

    def _slow_make_app() -> _StubApp:
        gate.wait(timeout=5)
        return _StubApp()

    monkeypatch.setattr(view, "_make_app", _slow_make_app)
    real_stdout = sys.stdout
    try:
        view.start()
        thread = view._thread
        assert thread is not None
        # Suspend while the application is still being constructed.
        view.suspend()
        gate.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        # The superseded startup never entered its run loop, never
        # installed the stream capture, and left no app behind.
        assert ran == []
        assert sys.stdout is real_stdout
        assert view._app is None
        assert view.running is False
    finally:
        gate.set()
        console_view._set_active(None)


def test_wait_line_returns_eof_when_the_app_died(monkeypatch) -> None:
    import threading

    from uagent.runtime.display_channel import OutputDocument

    view = ConsoleView(document=OutputDocument())

    class _DyingApp:
        def run(self) -> None:
            return None

        def exit(self) -> None:
            pass

    monkeypatch.setattr(view, "_make_app", lambda: _DyingApp())
    view.start()
    try:
        # Wait for the application thread to end on its own.
        deadline = time.monotonic() + 5
        while view.running and time.monotonic() < deadline:
            time.sleep(0.02)
        assert view.running is False
        results: list[object] = []
        waiter = threading.Thread(
            target=lambda: results.append(view.wait_line(abort=lambda: False)),
            daemon=True,
        )
        waiter.start()
        waiter.join(timeout=5)
        assert not waiter.is_alive()
        assert results == [view.eof_sentinel]
    finally:
        view.stop()
        console_view._set_active(None)


def test_completion_menu_is_part_of_the_layout():
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(
            pt_input=pipe,
            pt_output=DummyOutput(),
            document=document,
            completer=WordCompleter(["status", "start", "stop"]),
        )
        view.start()
        try:
            # Tab populates the completion state...
            pipe.send_text("st\t")
            assert _wait_for(lambda: view._input_buffer.complete_state is not None)
            state = view._input_buffer.complete_state
            assert state is not None
            assert len(state.completions) >= 3
            # ...and the layout carries a menu that renders them (the
            # legacy PromptSession shows one; without it the
            # candidates exist but stay invisible).
            containers: list[object] = []

            def _walk(container: object) -> None:
                containers.append(container)
                for child in container.get_children():
                    _walk(child)

            _walk(view._app.layout.container)
            assert any(isinstance(c, CompletionsMenu) for c in containers)
        finally:
            view.stop()


def test_view_status_follows_idle_transitions(monkeypatch):
    # Regression (PR #483 Codex P2): set_status() deliberately skips
    # print_status_line() for CLI IDLE transitions (the next prompt is
    # the legacy idle indicator), so the view only ever received BUSY
    # and its bottom line stayed "[STATE] BUSY [LLM]" after the turn.
    from uagent import core

    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.setattr(core, "human_ask_active", False)

    core.set_status(True, "LLM")
    core.set_status(False, "")

    assert fake.status[0] == ("[STATE] BUSY [LLM]", True)
    assert fake.status[-1] == ("[STATE] IDLE", False)


def test_stop_restores_streams_even_if_the_app_thread_lags(monkeypatch) -> None:
    # Regression (PR #483 CI): suspend() joined the application
    # thread with a 1s timeout and returned with the stream capture
    # still installed whenever the thread was slower than that —
    # the restored-terminal assert raced on loaded CI runners.
    # stop() must hand the real streams back deterministically.
    import sys
    import threading

    from uagent.runtime.display_channel import OutputDocument

    view = ConsoleView(document=OutputDocument())
    release = threading.Event()

    class _StubApp:
        loop = None

        def run(self) -> None:
            release.wait(timeout=10)

        def exit(self) -> None:
            pass

    monkeypatch.setattr(view, "_make_app", lambda: _StubApp())
    real_stdout, real_stderr = sys.stdout, sys.stderr
    try:
        view.start()
        assert _wait_for(lambda: isinstance(sys.stdout, console_view._ViewStreamProxy))
        view.stop()
        assert sys.stdout is real_stdout
        assert sys.stderr is real_stderr
    finally:
        release.set()
        thread = view._thread
        if thread is not None:
            thread.join(timeout=5)
        console_view._set_active(None)
    assert sys.stdout is real_stdout

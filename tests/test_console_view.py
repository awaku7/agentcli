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


def _queued_marker() -> str:
    from uagent.i18n import _

    return _(" (queued)")


def test_stream_proxy_does_not_import_during_interpreter_finalization(monkeypatch):
    proxy = console_view._ViewStreamProxy(object(), "output")
    monkeypatch.setattr(console_view.sys, "is_finalizing", lambda: True)

    # A newline posts immediately; a partial line posts when TextIOBase
    # finalizes and flushes the proxy. Neither may import during shutdown.
    proxy.write("complete line\n")
    proxy.write("partial line")
    proxy.flush()

    assert proxy._pending == ""


def test_view_submits_lines_and_projects_document():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert console_view.active_view() is view
            document.append("answer", "assistant text\n")
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

            view.set_usage(
                {
                    "input_tokens_delta": 1234,
                    "cache_read_input_tokens_delta": 300,
                    "output_tokens_delta": 567,
                    "total_tokens_delta": 1801,
                },
                session_id="session-a",
            )
            status = view._status_fragments()
            assert status[0][1] == "[STATE] BUSY [LLM]"
            assert "Session: in 1,234 / cached 300 / out 567" in status[1][1]

            view.set_usage(
                {
                    "input_tokens_delta": 10,
                    "cache_read_input_tokens_delta": 5,
                    "output_tokens_delta": 3,
                    "total_tokens_delta": 13,
                },
                session_id="session-a",
            )
            status = view._status_fragments()
            assert "Session: in 1,244 / cached 305 / out 570" in status[1][1]

            view.set_usage(
                {
                    "input_tokens_delta": 4,
                    "cache_read_input_tokens_delta": 1,
                    "output_tokens_delta": 5,
                    "total_tokens_delta": 9,
                },
                session_id="session-b",
            )
            status = view._status_fragments()
            assert "Session: in 4 / cached 1 / out 5" in status[1][1]
            assert len(status) == 2
        finally:
            view.stop()


def test_view_ignores_blank_enter_while_busy():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            view.set_status("[STATE] BUSY", busy=True)
            pipe.send_text("  ")
            assert _wait_for(lambda: view._input_buffer.text == "  ")
            pipe.send_text("\r")
            assert _wait_for(lambda: view._input_buffer.text == "")
            # Let the input event finish before inspecting the queue/document.
            time.sleep(0.1)
            assert view._submissions.empty()
            assert not any(
                _queued_marker() in segment.text for segment in document.snapshot()[0]
            )
        finally:
            view.stop()


def test_view_mouse_wheel_reaches_full_output_scrollback():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for i in range(1, 101):
        document.append("answer", f"line {i:03d}\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            for _ in range(40):
                pipe.send_text("\x1b[<64;1;2M")  # wheel up
            assert _wait_for(
                lambda: view._output_buffer.document.text[
                    : view._output_buffer.cursor_position
                ].count("\n")
                <= 1
            )

            for _ in range(40):
                pipe.send_text("\x1b[<65;1;2M")  # wheel down
            assert _wait_for(
                lambda: view._output_buffer.document.text[
                    : view._output_buffer.cursor_position
                ].count("\n")
                >= 95
            )
        finally:
            view.stop()


def test_right_click_paste_replaces_selected_input_text(monkeypatch):
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from uagent.cli_impl import console_view

    monkeypatch.setattr(console_view, "_read_system_clipboard", lambda: "replacement")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            assert _wait_for(lambda: view._app is not None and view.running)
            pipe.send_text("draft text")
            assert _wait_for(lambda: view._input_buffer.text == "draft text")
            buffer = view._input_buffer
            buffer.cursor_position = 0
            buffer.start_selection()
            buffer.cursor_position = len("draft")

            input_y = view._app.output.get_size().rows - 2
            pipe.send_text(f"\x1b[<2;1;{input_y}M")
            pipe.send_text(f"\x1b[<2;1;{input_y}m")
            assert _wait_for(lambda: buffer.text == "replacement text")
        finally:
            view.stop()


@pytest.mark.parametrize("paste_method", ["ctrl-v", "right-click"])
def test_input_pastes_system_clipboard(paste_method, monkeypatch):
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from uagent.cli_impl import console_view

    monkeypatch.setattr(console_view, "_read_system_clipboard", lambda: "one\r\ntwo")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            assert _wait_for(lambda: view._app is not None and view.running)
            if paste_method == "ctrl-v":
                pipe.send_text("\x16")
            else:
                rows = view._app.output.get_size().rows
                input_y = rows - 2
                pipe.send_text(f"\x1b[<2;1;{input_y}M")
                pipe.send_text(f"\x1b[<2;1;{input_y}m")
            assert _wait_for(lambda: view._input_buffer.text == "one\ntwo")
        finally:
            view.stop()


@pytest.mark.parametrize(
    ("selection_target", "selected_text"),
    [("input", "draft"), ("output", "history")],
)
def test_ctrl_c_copies_a_selection_without_interrupting(
    selection_target, selected_text
):
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    document.append("answer", "history text\n")
    interrupts = []
    with create_pipe_input() as pipe:
        view = ConsoleView(
            pt_input=pipe,
            pt_output=DummyOutput(),
            document=document,
            on_ctrl_c=lambda: interrupts.append(True),
        )
        view.start()
        try:
            assert _wait_for(lambda: view._app is not None and view.running)
            if selection_target == "input":
                pipe.send_text("draft text")
                assert _wait_for(lambda: view._input_buffer.text == "draft text")
                buffer = view._input_buffer
                end = len(selected_text)
            else:
                assert _wait_for(lambda: "history text" in view._output_text)
                buffer = view._output_buffer
                end = len(selected_text)

            buffer.cursor_position = 0
            buffer.start_selection()
            buffer.cursor_position = end
            pipe.send_text("\x03")

            assert _wait_for(
                lambda: view._app.clipboard.get_data().text == selected_text
            )
            assert buffer.selection_state is not None
            assert interrupts == []

            buffer.exit_selection()
            pipe.send_text("\x03")
            assert _wait_for(lambda: interrupts == [True])
        finally:
            view.stop()
        assert console_view.active_view() is None


def test_usage_status_defaults_on_and_can_be_disabled(monkeypatch):
    from types import SimpleNamespace

    import uagent.core  # noqa: F401  (load core before its display helper)
    from uagent.core_impl import display

    seen = []
    view = SimpleNamespace(
        set_usage=lambda usage, **kwargs: seen.append((usage, kwargs))
    )
    monkeypatch.setattr(display, "_active_console_view", lambda: view)
    monkeypatch.setattr(display, "env_get", lambda _name, default="": default)
    monkeypatch.setattr(
        display._core, "_session_store_active_id", "session-a", raising=False
    )

    assert display.usage_display_enabled() is True
    usage = {"input_tokens_delta": 12}
    assert display.set_usage_status(usage) is True
    assert seen == [(usage, {"session_id": "session-a"})]

    monkeypatch.setattr(display, "env_get", lambda _name, _default="": "0")
    assert display.usage_display_enabled() is False
    assert display.set_usage_status(usage) is False
    assert seen == [(usage, {"session_id": "session-a"}), (None, {})]


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
            document.append("reasoning", "deep thought\n")
            document.append("answer", "the answer")
            assert _wait_for(lambda: "the answer" in view._output_text)
            segments, _v, _e = document.snapshot()
            assert [(s.kind, s.text) for s in segments] == [
                ("reasoning", "deep thought\n"),
                ("answer", "the answer"),
            ]
            fragments = view._lexer.lex_document(Document(view._output_text))(0)
            assert ("ansibrightblack", "deep thought") in fragments
            answer_fragments = view._lexer.lex_document(Document(view._output_text))(1)
            assert ("", "the answer") in answer_fragments
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


def test_print_status_line_routes_to_view_during_ask(monkeypatch):
    # An IDLE transition printed while a human_ask is active
    # must still reach the (suspended) view: the suppression
    # protects the legacy ask prompt, and dropping the update
    # loses it for good — the state has already changed, so
    # nothing prints it again, and the resumed view would keep
    # showing the stale BUSY [tool:human_ask] line.
    from uagent import core

    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    try:
        with core.status_lock:
            core.status_busy = False
            core.status_label = ""
        with core.human_ask_lock:
            core.human_ask_active = True
        core.print_status_line()
        assert fake.status == [("[STATE] IDLE", False)]
    finally:
        with core.human_ask_lock:
            core.human_ask_active = False


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

    last_pending_token = None

    def wait_line(self, *, abort):
        if isinstance(self._item, BaseException):
            raise self._item
        return self._item


def test_read_line_from_view_returns_submitted_line():
    from uagent.cli_impl import stdin_loop

    view = _StubView("typed line")
    assert stdin_loop._read_line_from_view(view, "prompt> ") == ("typed line", None)  # type: ignore[arg-type]


def test_read_line_from_view_abort_suspends():
    from uagent.cli_impl import stdin_loop

    view = _StubView(None)
    assert stdin_loop._read_line_from_view(view, "prompt> ") == (None, None)  # type: ignore[arg-type]
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
        assert first_thread is not None
        assert _wait_for(lambda: not first_thread.is_alive())


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
    import os
    import select as select_module
    import sys
    import types

    if os.name == "nt":
        pytest.skip("POSIX interrupt monitor is not used on Windows")

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
        def run(self, pre_run=None) -> None:
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
    from uagent.core_impl import status as core_status

    fake = _FakeView()
    console_view._set_active(fake)  # type: ignore[arg-type]
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(
        core_status, "normalize_status_label", lambda _busy, label: label
    )

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

        def run(self, pre_run=None) -> None:
            if pre_run is not None:
                pre_run()
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


def test_view_capture_redirects_preexisting_stderr_handlers():
    # Regression (PR #483 Codex P2): a logging handler created before
    # the view starts (the UAGENT_DEBUG_EVENTS event logger) holds
    # the original stderr; replacing sys.stderr alone left it writing
    # onto the full-screen terminal and out of the transcript.  The
    # capture redirects such handlers to the proxy and restores them
    # on stop.
    import io
    import logging
    import sys

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    terminal = io.StringIO()
    logger = logging.getLogger("uagent.test.capture_redirect")
    handler = logging.StreamHandler(terminal)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    real_stdout, real_stderr = sys.stdout, sys.stderr
    sys.stderr = terminal
    try:
        with create_pipe_input() as pipe:
            view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
            view.start()
            try:
                assert _wait_for(
                    lambda: isinstance(sys.stderr, console_view._ViewStreamProxy)
                )
                # The redirect walks every registered logger, which
                # can take a moment in a large process; wait for it
                # instead of asserting the moment the proxy appears.
                assert _wait_for(lambda: handler.stream is sys.stderr)
                logger.info("event while captured")
                segments, _v, _e = dc.default_document().snapshot()
                text = "".join(s.text for s in segments)
                assert "event while captured" in text
                assert "event while captured" not in terminal.getvalue()
            finally:
                view.stop()
            assert _wait_for(lambda: handler.stream is terminal)
            logger.info("event after restore")
            assert "event after restore" in terminal.getvalue()
    finally:
        logger.removeHandler(handler)
        sys.stdout, sys.stderr = real_stdout, real_stderr


def test_view_capture_redirects_handlers_bound_before_the_startup_tee():
    # The event logger is configured before main() installs the
    # startup tee, so its handler holds the stream the tee wraps,
    # not sys.stderr itself.  The capture must redirect it too —
    # otherwise its events write onto the full-screen terminal.
    # On restore the handler lands on the captured stream (the
    # tee), which forwards to the same terminal.
    import io
    import logging
    import sys

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    terminal = io.StringIO()
    logger = logging.getLogger("uagent.test.capture_redirect_tee")
    handler = logging.StreamHandler(terminal)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    real_stdout, real_stderr = sys.stdout, sys.stderr
    tee = console_view._StartupOutputTee(terminal, [], False)
    sys.stderr = tee
    try:
        with create_pipe_input() as pipe:
            view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
            view.start()
            try:
                assert _wait_for(
                    lambda: isinstance(sys.stderr, console_view._ViewStreamProxy)
                )
                assert _wait_for(lambda: handler.stream is sys.stderr)
                logger.info("event while captured")
                segments, _v, _e = dc.default_document().snapshot()
                text = "".join(s.text for s in segments)
                assert "event while captured" in text
                assert "event while captured" not in terminal.getvalue()
            finally:
                view.stop()
            assert _wait_for(lambda: handler.stream is tee)
            logger.info("event after restore")
            assert "event after restore" in terminal.getvalue()
    finally:
        logger.removeHandler(handler)
        sys.stdout, sys.stderr = real_stdout, real_stderr


def test_view_arrow_keys_navigate_history():
    # The input buffer carries the legacy prompt's history: Up/Down
    # walk it in place, like the legacy prompt.
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    history = InMemoryHistory()
    history.append_string("first command")
    history.append_string("second command")
    with create_pipe_input() as pipe:
        view = ConsoleView(
            history=history,
            document=dc.OutputDocument(),
            pt_input=pipe,
            pt_output=DummyOutput(),
        )
        view.start()
        try:
            assert _wait_for(lambda: view._app is not None and view.running)
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            pipe.send_text("\x1b[A")
            assert _wait_for(lambda: view._input_buffer.text == "second command")
            pipe.send_text("\x1b[A")
            assert _wait_for(lambda: view._input_buffer.text == "first command")
            pipe.send_text("\x1b[B")
            assert _wait_for(lambda: view._input_buffer.text == "second command")
        finally:
            view.stop()


def test_view_bracketed_paste_inserts_without_submitting():
    # A multi-line paste lands in the input buffer as one block —
    # it does not submit line by line — and Enter then submits the
    # whole block as a single item.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        view = ConsoleView(
            document=dc.OutputDocument(),
            pt_input=pipe,
            pt_output=DummyOutput(),
        )
        view.start()
        try:
            assert _wait_for(lambda: view._app is not None and view.running)
            pipe.send_text("\x1b[200~line one\nline two\nline three\x1b[201~")
            assert _wait_for(lambda: "line three" in view._input_buffer.text)
            assert view._submissions.empty()
            pipe.send_text("\r")
            item = view._submissions.get(timeout=5)
            assert item == ("line one\nline two\nline three", None)
        finally:
            view.stop()


def _busy_view(pipe, document, **kwargs):
    """A started view whose status says a turn is running."""
    from prompt_toolkit.output import DummyOutput

    view = ConsoleView(
        pt_input=pipe, pt_output=DummyOutput(), document=document, **kwargs
    )
    view.start()
    assert _wait_for(lambda: view._app is not None and view.running)
    view.set_prompt_text("User> ")
    view.set_status("[STATE] BUSY [LLM]", busy=True)
    return view


def test_view_message_during_generation_queues_after_no():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text("hello later\r")
            # The confirmation opens; nothing is queued or echoed yet.
            assert _wait_for(lambda: view._confirm_text == "hello later")
            assert view._submissions.empty()
            assert "hello later" not in _document_text(document)
            pipe.send_text("n")
            line = view.wait_line(abort=lambda: False)
            assert line == "hello later"
            token = view.last_pending_token
            assert token is not None
            assert any(
                s.kind == "user" and s.text == f"User> hello later{_queued_marker()}\n"
                for s in document.snapshot()[0]
            )
            # Dispatch resolves the marker.
            view.resolve_pending(token)
            assert any(
                s.kind == "user" and s.text == "User> hello later\n"
                for s in document.snapshot()[0]
            )
        finally:
            view.stop()


def test_view_message_during_generation_enter_interrupts():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    interrupts: list[bool] = []
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document, on_interrupt=lambda: interrupts.append(True))
        try:
            # Queue a command first so the priority order is visible.
            pipe.send_text(":status\r")
            assert _wait_for(lambda: not view._submissions.empty())
            pipe.send_text("stop and do this\r")
            assert _wait_for(lambda: view._confirm_text == "stop and do this")
            pipe.send_text("\r")
            assert _wait_for(lambda: interrupts == [True])
            # The interrupt line is returned ahead of the queued one,
            # and its echo is an ordinary user line (no marker).
            assert view.wait_line(abort=lambda: False) == "stop and do this"
            assert view.last_pending_token is None
            assert view.wait_line(abort=lambda: False) == ":status"
            assert view.last_pending_token is not None
            assert any(
                s.kind == "user" and s.text == "User> stop and do this\n"
                for s in document.snapshot()[0]
            )
        finally:
            view.stop()


def test_view_command_during_generation_queues_without_confirmation():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text(":some command\r")
            assert _wait_for(lambda: not view._submissions.empty())
            assert view._confirm_text is None
            assert view.wait_line(abort=lambda: False) == ":some command"
            assert view.last_pending_token is not None
            assert any(
                s.kind == "user"
                and s.text == f"User> :some command{_queued_marker()}\n"
                for s in document.snapshot()[0]
            )
        finally:
            view.stop()


def test_view_confirmation_preempted_by_suspend_queues_with_notice():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text("a question\r")
            assert _wait_for(lambda: view._confirm_text == "a question")
            # A human_ask taking the terminal suspends the view; the
            # open confirmation is cancelled into the queue, never
            # into an interrupt, and the transcript says so.
            view.suspend()
            assert view.wait_line(abort=lambda: False) == "a question"
            assert view.last_pending_token is not None
            text = _document_text(document)
            assert f"User> a question{_queued_marker()}\n" in text
            from uagent.i18n import _

            assert (
                _(
                    "The interrupt confirmation was cancelled, "
                    "so the message was queued."
                )
                in text
            )
        finally:
            view.stop()


def test_view_confirmation_queues_when_the_turn_ends():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text("late message\r")
            assert _wait_for(lambda: view._confirm_text == "late message")
            view.set_status("[STATE] IDLE", busy=False)
            assert view.wait_line(abort=lambda: False) == "late message"
            assert view.last_pending_token is not None
            assert view._confirm_text is None
        finally:
            view.stop()


def test_system_clipboard_write_never_raises():
    # The OS clipboard write is best-effort: whatever the
    # platform offers, the view must survive the attempt.
    from uagent.cli_impl.console_view import _write_system_clipboard

    assert _write_system_clipboard("x") in (True, False)


def test_system_clipboard_windows_uses_console_window_owner(monkeypatch):
    # The Windows branch must open the clipboard with a real
    # owner window (the console window): with a NULL owner,
    # EmptyClipboard leaves the owner NULL and SetClipboardData
    # fails — after the previous contents were already erased.
    # The memory block is also filled before the clipboard is
    # opened, so early failures never touch the clipboard.
    import ctypes
    import sys
    import types

    from uagent.cli_impl.console_view import _write_system_clipboard

    calls: list = []
    buffer = ctypes.create_string_buffer(64)

    class _Func:
        def __init__(self, name, result):
            self.name = name
            self.result = result

        def __call__(self, *args):
            calls.append((self.name, args))
            return self.result

    kernel32 = types.SimpleNamespace(
        GlobalAlloc=_Func("GlobalAlloc", 4242),
        GlobalLock=_Func("GlobalLock", ctypes.addressof(buffer)),
        GlobalUnlock=_Func("GlobalUnlock", True),
        GlobalFree=_Func("GlobalFree", None),
        GetConsoleWindow=_Func("GetConsoleWindow", 777),
    )
    user32 = types.SimpleNamespace(
        OpenClipboard=_Func("OpenClipboard", True),
        EmptyClipboard=_Func("EmptyClipboard", True),
        SetClipboardData=_Func("SetClipboardData", 4242),
        CloseClipboard=_Func("CloseClipboard", True),
    )
    monkeypatch.setattr(
        ctypes,
        "windll",
        types.SimpleNamespace(user32=user32, kernel32=kernel32),
        raising=False,
    )
    monkeypatch.setattr(sys, "platform", "win32")
    assert _write_system_clipboard("hi") is True
    names = [name for name, _args in calls]
    assert names.index("GlobalAlloc") < names.index("OpenClipboard")
    assert ("OpenClipboard", (777,)) in calls
    assert ("SetClipboardData", (13, 4242)) in calls
    written = buffer.raw[:6]
    assert written == "hi".encode("utf-16-le") + b"\x00\x00"


def test_system_clipboard_windows_reads_unicode_text(monkeypatch):
    import ctypes
    import sys
    import types

    from uagent.cli_impl.console_view import _read_system_clipboard

    calls: list = []

    class _Func:
        def __init__(self, name, result):
            self.name = name
            self.result = result

        def __call__(self, *args):
            calls.append((self.name, args))
            return self.result

    kernel32 = types.SimpleNamespace(
        GetConsoleWindow=_Func("GetConsoleWindow", 777),
        GlobalLock=_Func("GlobalLock", 888),
        GlobalUnlock=_Func("GlobalUnlock", True),
    )
    user32 = types.SimpleNamespace(
        OpenClipboard=_Func("OpenClipboard", True),
        GetClipboardData=_Func("GetClipboardData", 999),
        CloseClipboard=_Func("CloseClipboard", True),
    )
    monkeypatch.setattr(
        ctypes,
        "windll",
        types.SimpleNamespace(user32=user32, kernel32=kernel32),
        raising=False,
    )
    monkeypatch.setattr(ctypes, "wstring_at", lambda _pointer: "clipboard 日本語")
    monkeypatch.setattr(sys, "platform", "win32")

    assert _read_system_clipboard() == "clipboard 日本語"
    assert ("OpenClipboard", (777,)) in calls
    assert ("GetClipboardData", (13,)) in calls
    assert ("GlobalLock", (999,)) in calls
    assert ("GlobalUnlock", (999,)) in calls
    assert ("CloseClipboard", ()) in calls


def test_startup_output_capture_and_seed(monkeypatch):
    # Startup prints happen before the view exists and would be
    # hidden once the view takes over the terminal.  The tee
    # forwards them unchanged and keeps a copy; seeding posts
    # the copy into the document (stdout as output, stderr as
    # debug), and draining empties the buffers.
    import io
    import sys

    from uagent.cli_impl import console_view
    from uagent.runtime import display_channel

    out_sink = io.StringIO()
    err_sink = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out_sink)
    monkeypatch.setattr(sys, "stderr", err_sink)
    try:
        console_view.install_startup_output_capture()
        console_view.install_startup_output_capture()  # idempotent
        print("WELCOME BANNER")
        print("a warning", file=sys.stderr)
        assert out_sink.getvalue() == "WELCOME BANNER\n"
        assert err_sink.getvalue() == "a warning\n"

        posted: list = []
        monkeypatch.setattr(
            display_channel,
            "post_segment",
            lambda kind, text: posted.append((kind, text)),
        )
        console_view.seed_document_from_startup_output()
        assert posted == [
            ("output", "WELCOME BANNER\n"),
            ("debug", "a warning\n"),
        ]
        assert console_view.take_startup_output() == ("", "")
    finally:
        console_view.take_startup_output()


def test_system_clipboard_write_uses_a_native_tool(monkeypatch, tmp_path):
    # No third-party dependency is required: a native clipboard
    # tool on PATH (xclip here, standing in for pbcopy/wl-copy)
    # receives the text.
    import os
    import stat
    import sys

    if sys.platform == "win32":
        return
    from uagent.cli_impl.console_view import _write_system_clipboard

    sink = tmp_path / "clipboard.txt"
    tool = tmp_path / "xclip"
    tool.write_text(f"#!/bin/sh\ncat > {sink}\n")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    assert _write_system_clipboard("copied text") is True
    assert sink.read_text() == "copied text"


def test_view_submit_racing_the_turn_end_never_wedges_the_confirmation():
    # The busy check and the confirmation installation are one
    # atomic step.  If the turn ends in between, the BUSY->IDLE
    # transition resolves a confirmation that does not exist yet
    # and the one installed after sits at an idle prompt forever:
    # input read-only, the message undispatched.
    import threading

    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            real_lock = view._state_lock
            entered = threading.Event()

            class _RendezvousLock:
                def __enter__(self):
                    real_lock.acquire()
                    entered.set()
                    return self

                def __exit__(self, *exc):
                    real_lock.release()
                    return False

            view._state_lock = _RendezvousLock()
            pipe.send_text("race me\r")
            assert entered.wait(timeout=5)
            # The turn ends while the submission is in flight.
            end_turn = threading.Thread(
                target=lambda: view.set_status("[STATE] IDLE", busy=False)
            )
            end_turn.start()
            end_turn.join(timeout=5)
            view._state_lock = real_lock
            # Whichever side won the lock, the outcome is the same:
            # no confirmation is left open, and the line dispatches
            # (as a queued line if the question was installed and
            # then resolved, as a plain one if the turn ended first).
            assert view._confirm_text is None
            assert view.wait_line(abort=lambda: False) == "race me"
        finally:
            view.stop()


def test_view_rule_carries_the_prompt_label_not_the_input_line():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from prompt_toolkit.utils import get_cwidth

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(lambda: view._app is not None and view.running)
            view.set_prompt_text("UAGEXE> ")
            upper = "".join(text for _style, text in view._upper_rule_fragments())
            # The where-am-I label rides inside the upper rule; the
            # trailing ">" of the prompt string is dropped.
            assert upper.startswith("── UAGEXE ")
            assert get_cwidth(upper) == 80
            lower = "".join(text for _style, text in view._lower_rule_fragments())
            assert set(lower) == {"─"}
            assert get_cwidth(lower) == 80
        finally:
            view.stop()


def test_view_wheel_over_the_input_scrolls_the_output():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for i in range(1, 41):
        document.append("answer", f"line {i:02d}\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            top = window.vertical_scroll
            assert top > 0  # the transcript starts scrolled to the tail
            rows = view._app.output.get_size().rows
            input_y = rows - 2  # the single input line
            cursor_before = view._output_buffer.cursor_position
            for _ in range(2):
                pipe.send_text(f"\x1b[<64;5;{input_y}M")
            assert _wait_for(
                lambda: view._output_buffer.cursor_position < cursor_before
            )
            cursor_after_up = view._output_buffer.cursor_position
            for _ in range(2):
                pipe.send_text(f"\x1b[<65;5;{input_y}M")
            assert _wait_for(
                lambda: view._output_buffer.cursor_position > cursor_after_up
            )
        finally:
            view.stop()


def test_view_drag_on_the_output_copies_the_selection():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    document.append("answer", "alpha bravo charlie\ndelta echo foxtrot\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            pipe.send_text("\x1b[<0;1;1M")
            assert _wait_for(lambda: view._output_buffer.cursor_position == 0)
            pipe.send_text("\x1b[<32;6;1M")
            assert _wait_for(lambda: view._output_buffer.selection_state is not None)
            pipe.send_text("\x1b[<0;6;1m")
            assert _wait_for(lambda: view._app.clipboard.get_data().text == "alpha")
        finally:
            view.stop()


def test_view_drag_at_the_top_edge_autoscrolls_and_extends():
    # Holding a drag at the output's top edge scrolls the view
    # and keeps extending the selection upward, so text above
    # the visible area can be selected and copied.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for i in range(1, 41):
        document.append("answer", f"line {i:02d}\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            top = window.vertical_scroll
            assert top > 0  # the transcript starts scrolled to the tail
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;2M")  # press on the second visible row
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            press_row, _ = view._output_buffer.document.translate_index_to_position(
                view._output_buffer.cursor_position
            )
            for _ in range(8):
                pipe.send_text("\x1b[<32;1;1M")  # hold at the top edge
            assert _wait_for(lambda: window.vertical_scroll < top - 2)
            state = view._output_buffer.selection_state
            assert state is not None
            start = min(
                state.original_cursor_position, view._output_buffer.cursor_position
            )
            start_row, _ = view._output_buffer.document.translate_index_to_position(
                start
            )
            # The selection reached above the first visible row.
            assert start_row < press_row - 1
            pipe.send_text("\x1b[<0;1;1m")
            assert _wait_for(
                lambda: view._app.clipboard.get_data().text.startswith(
                    f"line {start_row + 1:02d}"
                )
            )
            copied = view._app.clipboard.get_data().text
            # The press anchored the selection at the start of its
            # line, so the copy ends with the line just above it.
            assert copied.endswith(f"line {press_row:02d}\n")
        finally:
            view.stop()


def test_view_drag_held_at_the_edge_keeps_scrolling_without_events():
    # A stationary pointer sends no mouse events: once the drag
    # is pinned at the edge, the view must keep scrolling and
    # extending on its own until the button is released.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for i in range(1, 41):
        document.append("answer", f"line {i:02d}\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            top = window.vertical_scroll
            assert top > 0
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;2M")  # press on the second visible row
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            pipe.send_text("\x1b[<32;1;1M")  # move to the top row
            pipe.send_text("\x1b[<32;1;1M")  # pin at the edge, then hold still
            # No further events: the scroll advances by itself.
            assert _wait_for(lambda: window.vertical_scroll <= top - 3)
            assert view._output_buffer.selection_state is not None
            start_row, _ = view._output_buffer.document.translate_index_to_position(
                view._output_buffer.cursor_position
            )
            assert start_row < top - 2
            pipe.send_text("\x1b[<0;1;1m")
            assert _wait_for(
                lambda: view._app.clipboard.get_data().text.startswith("line ")
            )
        finally:
            view.stop()


def test_view_drag_held_at_bottom_edge_keeps_scrolling_without_events():
    # The reverse edge must advance the viewport and the selection
    # endpoint too; this catches asymmetric downward drag handling.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for i in range(1, 81):
        document.append("answer", f"line {i:02d}\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            view._scroll_output_lines(-1000)
            assert _wait_for(lambda: window.vertical_scroll == 0)
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;2M")  # press on the second visible row
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            bottom_y = window.render_info.window_height
            pipe.send_text(f"\x1b[<32;1;{bottom_y}M")
            pipe.send_text(f"\x1b[<32;1;{bottom_y}M")  # pin, then hold at bottom
            assert _wait_for(lambda: window.vertical_scroll >= 3)
            assert view._output_buffer.selection_state is not None
            cursor_row, _ = view._output_buffer.document.translate_index_to_position(
                view._output_buffer.cursor_position
            )
            assert cursor_row > bottom_y
            pipe.send_text(f"\x1b[<0;1;{bottom_y}m")
            assert _wait_for(lambda: view._output_control._edge_task is None)
        finally:
            view.stop()


def test_view_drag_released_outside_the_output_stops_edge_scrolling():
    # Mouse events go to the control under the pointer, so a
    # release over the spinner row never reaches the output's
    # handler.  It must still end the edge-scroll repeat —
    # otherwise the view keeps scrolling after the drag is over.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for i in range(1, 41):
        document.append("answer", f"line {i:02d}\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            top = window.vertical_scroll
            assert top > 0
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;2M")
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            pipe.send_text("\x1b[<32;1;1M")
            pipe.send_text("\x1b[<32;1;1M")  # pin at the edge; repeat starts
            assert _wait_for(lambda: window.vertical_scroll < top)
            rows = view._app.output.get_size().rows
            spinner_y = rows - 4  # the row just below the output area
            pipe.send_text(f"\x1b[<0;1;{spinner_y}m")  # release over the spinner
            assert _wait_for(lambda: view._output_control._edge_task is None)
            settled = window.vertical_scroll
            import time as _time

            _time.sleep(0.6)
            assert window.vertical_scroll == settled
        finally:
            view.stop()


def test_view_drag_on_a_wrapped_lines_middle_row_is_not_the_edge():
    # A wrapped line spans several screen rows.  Only its first
    # screen row is the top edge: dragging on a middle segment
    # must not start the edge-scroll repeat, while the true top
    # row still does.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for _ in range(15):
        document.append("answer", "W" * 183 + "\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            top = window.vertical_scroll
            assert top > 0
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;3M")  # press on the third screen row
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            pipe.send_text("\x1b[<32;1;2M")  # middle segment of the top line
            pipe.send_text("\x1b[<32;1;2M")
            import time as _time

            _time.sleep(0.8)  # past the repeat's initial delay
            assert view._output_control._edge_task is None
            assert window.vertical_scroll == top
            # The true top row still starts the repeat.
            pipe.send_text("\x1b[<32;1;1M")
            pipe.send_text("\x1b[<32;1;1M")
            assert _wait_for(lambda: window.vertical_scroll < top)
            pipe.send_text("\x1b[<0;1;1m")
            assert _wait_for(lambda: view._output_control._edge_task is None)
        finally:
            view.stop()


def test_view_drag_at_the_top_edge_when_the_view_starts_mid_line():
    # When the viewport starts partway through a wrapped line,
    # the render mapping also carries the off-screen segments
    # above it (negative keys).  The first actual screen row
    # must still count as the top edge.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for i in range(20):
        document.append("answer", f"line {i:02d}\n")
    document.append("answer", "W" * 4000)
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            # The cursor sits on the huge last line, so the window
            # scrolls inside it: the mapping carries the segments
            # above the viewport under negative keys.
            assert _wait_for(
                lambda: min(window.render_info.visible_line_to_row_col) < 0
            )
            inner_top = window.vertical_scroll_2
            assert inner_top > 0
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;2M")
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            pipe.send_text("\x1b[<32;1;1M")
            pipe.send_text("\x1b[<32;1;1M")  # pin at the top edge
            assert _wait_for(lambda: window.vertical_scroll_2 < inner_top)
            pipe.send_text("\x1b[<0;1;1m")
            assert _wait_for(lambda: view._output_control._edge_task is None)
        finally:
            view.stop()


def test_view_drag_at_the_edge_of_a_single_huge_line_scrolls_within_it():
    # A single paragraph taller than the viewport: the top edge
    # must keep scrolling through its wrapped segments instead
    # of stopping at the first visible one — the document row
    # is already 0, but segments remain above.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    document.append("answer", "W" * 4000)
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            assert _wait_for(lambda: window.vertical_scroll_2 > 0)
            inner_top = window.vertical_scroll_2
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;2M")
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            top_endpoint = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<32;1;1M")
            pipe.send_text("\x1b[<32;1;1M")  # pin at the top edge
            # The repeat steps the endpoint segment by segment
            # toward the paragraph's start, and the view follows.
            assert _wait_for(
                lambda: view._output_buffer.cursor_position < top_endpoint
                and window.vertical_scroll_2 < inner_top
            )
            pipe.send_text("\x1b[<0;1;1m")
            assert _wait_for(lambda: view._output_control._edge_task is None)
        finally:
            view.stop()


def test_view_drag_crossing_into_a_wrapped_line_enters_its_nearest_segment():
    # Crossing a line boundary at the edge must enter the
    # neighbouring wrapped line at its nearest segment — one
    # screen row — not jump to its far end and select the
    # whole paragraph in one tick.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    document.append("answer", "W" * 4000 + "\n")
    for i in range(40):
        document.append("answer", f"line {i:02d}\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            # Bring the first short line (document row 1, starting
            # at index 4001) to the top of the viewport.
            view._output_buffer.cursor_position = 4001
            assert _wait_for(
                lambda: window.render_info.visible_line_to_row_col.get(0) == (1, 0)
            )
            pipe.send_text("\x1b[<0;1;1M")  # press at its start
            pipe.send_text("\x1b[<32;1;1M")  # pinned at the top edge
            # The extension crosses into the paragraph's LAST
            # segment (index 3920), then steps segment by
            # segment; it never lands on 0 in one jump.
            assert _wait_for(lambda: 0 < view._output_buffer.cursor_position < 4001)
            pipe.send_text("\x1b[<0;1;1m")
            assert _wait_for(lambda: view._output_control._edge_task is None)
        finally:
            view.stop()


def test_view_drag_at_the_edge_of_a_wide_char_line_scrolls_within_it():
    # Same as the huge-line case, but with double-width
    # characters: the render map's segment starts are
    # terminal-cell offsets while mouse events and the document
    # use character offsets.  The edge detection must convert
    # between them, or the top edge is never recognized.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    document.append("answer", "界" * 4000)
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            assert _wait_for(lambda: window.vertical_scroll_2 > 0)
            inner_top = window.vertical_scroll_2
            initial_cursor = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<0;1;2M")
            assert _wait_for(
                lambda: view._output_buffer.cursor_position != initial_cursor
            )
            top_endpoint = view._output_buffer.cursor_position
            pipe.send_text("\x1b[<32;1;1M")
            pipe.send_text("\x1b[<32;1;1M")  # pin at the top edge
            assert _wait_for(
                lambda: view._output_buffer.cursor_position < top_endpoint
                and window.vertical_scroll_2 < inner_top
            )
            pipe.send_text("\x1b[<0;1;1m")
            assert _wait_for(lambda: view._output_control._edge_task is None)
        finally:
            view.stop()


def test_view_drag_at_the_bottom_edge_steps_through_unrendered_segments():
    # A wrapped line extending below the viewport: the render
    # map covers only its rendered prefix, but the downward
    # extension must still step segment by segment through the
    # unrendered part instead of jumping to the line's end.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    document.append("answer", "W" * 10000)
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            # Start from the line's beginning.
            view._output_buffer.cursor_position = 0
            assert _wait_for(lambda: window.vertical_scroll_2 == 0)
            rows = view._app.output.get_size().rows
            bottom_y = rows - 5  # the output area's last screen row
            pipe.send_text("\x1b[<0;1;1M")  # press at the top
            pipe.send_text(f"\x1b[<32;1;{bottom_y}M")  # drag to the bottom edge
            assert _wait_for(lambda: view._output_buffer.cursor_position > 0)
            first_endpoint = view._output_buffer.cursor_position
            assert first_endpoint < 10000
            pipe.send_text(f"\x1b[<32;1;{bottom_y}M")  # pin at the edge
            assert _wait_for(
                lambda: view._output_buffer.cursor_position > first_endpoint
            )
            # Stepping, not jumping to the end of the line.
            assert view._output_buffer.cursor_position < 6000
            pipe.send_text(f"\x1b[<0;1;{bottom_y}m")
            assert _wait_for(lambda: view._output_control._edge_task is None)
        finally:
            view.stop()


def test_view_completes_while_typing_like_the_legacy_prompt():
    # The legacy PromptSession completes while typing; the view
    # must offer candidates the same way, without waiting for Tab.
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    class _Completer(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            for candidate in (":head", ":help"):
                if candidate.startswith(text):
                    yield Completion(candidate, start_position=-len(text))

    with create_pipe_input() as pipe:
        view = ConsoleView(
            pt_input=pipe, pt_output=DummyOutput(), completer=_Completer()
        )
        view.start()
        try:
            pipe.send_text(":he")
            assert _wait_for(
                lambda: view._input_buffer.complete_state is not None
                and [c.text for c in view._input_buffer.complete_state.completions]
                == [":head", ":help"]
            )
        finally:
            view.stop()


def test_view_reply_mode_delivers_the_answer_and_restores_the_draft():
    # A human_ask is answered in the view: the screen never
    # switches, the reply is not a submission (no document echo,
    # no history entry), and the half-typed draft comes back.
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from uagent.runtime.display_channel import OutputDocument

    document = OutputDocument()
    history = InMemoryHistory()
    with create_pipe_input() as pipe:
        view = ConsoleView(
            pt_input=pipe,
            pt_output=DummyOutput(),
            history=history,
            document=document,
        )
        view.start()
        try:
            pipe.send_text("my draft")
            assert _wait_for(lambda: view._input_buffer.text == "my draft")
            view.begin_reply("[REPLY] > ")
            assert _wait_for(lambda: view._reply_armed)
            assert view._input_buffer.text == ""
            assert view._rule_label() == "[REPLY]"
            pipe.send_text("yes please\r")
            assert view.wait_reply(abort=lambda: False) == "yes please"
            assert _wait_for(lambda: view._input_buffer.text == "my draft")
            assert history.get_strings() == []
            segments, _version, _epoch = document.snapshot()
            assert all("yes please" not in s.text for s in segments)
        finally:
            view.stop()


def test_view_password_reply_is_masked_and_never_recorded():
    # A password reply renders as asterisks, is delivered to the
    # waiter, and leaves no trace in the document or the history.
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from uagent.runtime.display_channel import OutputDocument

    document = OutputDocument()
    document.append("output", "Enter the API key\n")
    history = InMemoryHistory()
    with create_pipe_input() as pipe:
        view = ConsoleView(
            pt_input=pipe,
            pt_output=DummyOutput(),
            history=history,
            document=document,
        )
        view.start()
        try:
            view.begin_reply("[PASSWORD] > ", is_password=True)
            assert _wait_for(lambda: view._reply_armed)
            assert view._rule_label() == "[PASSWORD]"
            pipe.send_text("s3cret")
            assert _wait_for(lambda: view._input_buffer.text == "s3cret")
            control = None
            for window in view._app.layout.find_all_windows():
                candidate = getattr(window, "content", None)
                if getattr(candidate, "buffer", None) is view._input_buffer:
                    control = candidate
            assert control is not None
            line = control.create_content(80, 1).get_line(0)
            assert "".join(text for _style, text, *_ in line).strip() == "******"
            pipe.send_text("\r")
            assert view.wait_reply(abort=lambda: False) == "s3cret"
            assert history.get_strings() == []
            segments, _version, _epoch = document.snapshot()
            assert any("Enter the API key" in s.text for s in segments)
            assert all("s3cret" not in s.text for s in segments)
        finally:
            view.stop()


def test_view_reply_ctrl_c_cancels_and_restores_the_draft():
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            pipe.send_text("draft")
            assert _wait_for(lambda: view._input_buffer.text == "draft")
            view.begin_reply("[REPLY] > ")
            assert _wait_for(lambda: view._reply_armed)
            pipe.send_text("partial\x03")
            assert view.wait_reply(abort=lambda: False) is view.reply_cancelled
            assert _wait_for(lambda: view._input_buffer.text == "draft")
        finally:
            view.stop()


def test_view_reply_answered_elsewhere_drops_the_typed_text():
    # The reader stops waiting (the ask was answered from another
    # channel) and ends reply mode: the typed text is dropped, the
    # draft returns, and nothing stale leaks into the next ask.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            pipe.send_text("draft")
            assert _wait_for(lambda: view._input_buffer.text == "draft")
            view.begin_reply("[REPLY] > ")
            assert _wait_for(lambda: view._reply_armed)
            pipe.send_text("stale")
            assert _wait_for(lambda: view._input_buffer.text == "stale")
            view.end_reply()
            assert _wait_for(lambda: view._input_buffer.text == "draft")
            view.begin_reply("[REPLY] > ")
            assert _wait_for(lambda: view._reply_armed)
            pipe.send_text("real\r")
            assert view.wait_reply(abort=lambda: False) == "real"
        finally:
            view.stop()


def test_view_password_reply_cannot_be_undone_back_into_the_prompt():
    # Regression (PR #491 Codex P1): restoring the draft with
    # set_document() left the reply in the buffer's undo stack —
    # Ctrl+_ at the normal (unmasked) prompt brought the password
    # back visibly, and Enter could then send it.  The restore
    # now resets the buffer's editing state.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            pipe.send_text("draft")
            assert _wait_for(lambda: view._input_buffer.text == "draft")
            view.begin_reply("[PASSWORD] > ", is_password=True)
            assert _wait_for(lambda: view._reply_armed)
            pipe.send_text("s3cret\r")
            assert view.wait_reply(abort=lambda: False) == "s3cret"
            assert _wait_for(lambda: view._input_buffer.text == "draft")
            pipe.send_text("\x1f")
            assert _wait_for(lambda: view._input_buffer.text != "s3cret")
            time.sleep(0.2)
            assert view._input_buffer.text == "draft"
        finally:
            view.stop()


def test_view_reply_opening_over_a_confirmation_does_not_restore_its_text():
    # Regression (PR #491 Codex P2): begin_reply settled an open
    # confirmation as a queue entry but left its text in the
    # buffer, so the arming step stashed that already-queued text
    # as the "draft" and the restore after the reply handed it
    # back as editable input — Enter would submit it twice.
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text("next task\r")
            assert _wait_for(lambda: view._confirm_text == "next task")
            view.begin_reply("[REPLY] > ")
            assert _wait_for(lambda: view._reply_armed)
            # The confirmation settled as exactly one queue entry.
            assert view.wait_line(abort=lambda: False) == "next task"
            assert f"next task{_queued_marker()}" in _document_text(document)
            pipe.send_text("the answer\r")
            assert view.wait_reply(abort=lambda: False) == "the answer"
            assert _wait_for(lambda: view._reply_label is None)
            assert view._input_buffer.text == ""
        finally:
            view.stop()


def test_view_password_reply_keeps_text_out_of_the_clipboard():
    # Regression (PR #491 Codex P1, second round): the mouse-copy
    # guard did not cover prompt_toolkit's keyboard cut bindings —
    # Ctrl+A / Ctrl+K during a password reply wrote the plaintext
    # password to the (OS-mirroring) app clipboard, and Ctrl+Y
    # after the reply pasted it back visibly.  Clipboard writes
    # are frozen while a password reply is open.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            view.begin_reply("[PASSWORD] > ", is_password=True)
            assert _wait_for(lambda: view._reply_armed)
            pipe.send_text("s3cret")
            assert _wait_for(lambda: view._input_buffer.text == "s3cret")
            pipe.send_text("\x01\x0b")  # Ctrl+A, Ctrl+K: kill the line.
            assert _wait_for(lambda: view._input_buffer.text == "")
            assert "s3cret" not in view._app.clipboard.get_data().text
            pipe.send_text("\x19")  # Ctrl+Y must not bring it back.
            time.sleep(0.2)
            assert view._input_buffer.text == ""
            view.end_reply()
        finally:
            view.stop()


def test_view_reply_end_then_begin_survives_a_stalled_app_loop():
    # Regression (PR #491 Codex P2, second round): end_reply only
    # POSTED the restore, so when the reader immediately opened
    # the next ask's reply, begin_reply still saw the old label,
    # skipped arming, and the queued restore then cleared the NEW
    # mode's state — Enter submitted normal lines while the
    # reader blocked in wait_reply.  end_reply now waits until
    # the restore has run.
    import threading

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    gate = threading.Event()
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            # Wait for the real application AND its loop: before
            # the loop exists, _call_on_loop runs callbacks inline
            # on the caller and there is no loop to stall (on a
            # slow machine the app object appears first).
            assert _wait_for(
                lambda: view._app is not None
                and view._app.loop is not None
                and view.running,
                timeout=10,
            )
            view.begin_reply("[REPLY] > ")
            assert _wait_for(lambda: view._reply_armed)
            # Stall the application loop: callbacks posted now
            # (the restore included) queue behind this one.  Wait
            # until the stall is actually executing on the loop —
            # posting alone does not prove the loop is blocked.
            stall_started = threading.Event()

            def _stall() -> None:
                stall_started.set()
                gate.wait(5)

            view._call_on_loop(_stall)
            assert _wait_for(lambda: stall_started.is_set(), timeout=10)
            worker = threading.Thread(
                target=lambda: (view.end_reply(), view.begin_reply("[REPLY] > ")),
                daemon=True,
            )
            worker.start()
            # end_reply cannot return while its restore is queued
            # behind the stall: sample the worker for a while and
            # require it to stay blocked the whole time.
            for _ in range(10):
                time.sleep(0.05)
                assert worker.is_alive()
            gate.set()
            worker.join(timeout=5)
            assert not worker.is_alive()
            assert _wait_for(lambda: view._reply_armed)
            pipe.send_text("second answer\r")
            assert view.wait_reply(abort=lambda: False) == "second answer"
        finally:
            gate.set()
            view.stop()


def test_view_password_reply_ctrl_o_never_reaches_the_file_history(tmp_path):
    # Regression (PR #491 Codex P1, third round): the input buffer
    # kept the prompt's file-backed history during a password
    # reply, and prompt_toolkit's default Ctrl+O binding accepts
    # the buffer through validate_and_handle() — appending the
    # plaintext password to the history file and clearing the
    # buffer without delivering the reply.  Reply mode now swaps
    # in a throwaway history for the whole mode and treats
    # Ctrl+O as Enter.
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    history_file = tmp_path / "history"
    history = FileHistory(str(history_file))
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), history=history)
        view.start()
        try:
            view.begin_reply("[PASSWORD] > ", is_password=True)
            assert _wait_for(lambda: view._reply_armed)
            assert view._input_buffer.history is not history
            pipe.send_text("s3cret\x0f")
            deadline = time.monotonic() + 3
            item = view.wait_reply(abort=lambda: time.monotonic() > deadline)
            assert item == "s3cret"
            assert _wait_for(lambda: view._input_buffer.history is history)
            contents = (
                history_file.read_text(encoding="utf-8")
                if history_file.exists()
                else ""
            )
            assert "s3cret" not in contents
            assert "s3cret" not in history.get_strings()
        finally:
            view.stop()


def test_view_password_reply_never_lands_in_an_emacs_macro():
    # Regression (PR #491 Codex P2, fourth round): Emacs keyboard
    # macros live on the application, not the buffer, so the
    # reply's buffer reset left them untouched — a recording that
    # captured the password keystrokes could be replayed with
    # Ctrl+X e at the restored, unmasked prompt, inserting the
    # secret in the clear.  Arming a password reply stops any
    # recording in progress, and the restore drops macro state
    # the reply could have tainted.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput())
        view.start()
        try:
            assert _wait_for(lambda: view._app is not None and view.running)
            # A recording started BEFORE the ask is stopped at
            # arm time; its keys never reach a stored macro.
            pipe.send_text("\x18(")  # Ctrl+X ( : start recording.
            assert _wait_for(lambda: view._app.emacs_state.is_recording)
            view.begin_reply("[PASSWORD] > ", is_password=True)
            assert _wait_for(lambda: view._reply_armed)
            assert not view._app.emacs_state.is_recording
            pipe.send_text("s3cret\r")
            assert view.wait_reply(abort=lambda: False) == "s3cret"
            pipe.send_text("\x18e")  # Ctrl+X e: replay — nothing comes back.
            time.sleep(0.2)
            assert view._input_buffer.text == ""
            # A recording started DURING the reply is dropped at
            # the restore, even though it was properly ended.
            view.begin_reply("[PASSWORD] > ", is_password=True)
            assert _wait_for(lambda: view._reply_armed)
            pipe.send_text("\x18(hunter2\x18)")
            assert _wait_for(lambda: view._app.emacs_state.macro)
            pipe.send_text("\r")
            assert view.wait_reply(abort=lambda: False) == "hunter2"
            assert view._app.emacs_state.macro == []
            pipe.send_text("\x18e")
            time.sleep(0.2)
            assert view._input_buffer.text == ""
        finally:
            view.stop()


def test_view_drag_on_a_tabbed_lines_interior_row_is_not_the_edge():
    # Tabs render as ^I (2 cells) but get_cwidth counts them as
    # 0, so converting segment offsets with plain character
    # widths drifts: an interior wrapped row of a tabbed line
    # must not be mistaken for the top edge, while the true
    # first row still is the edge.
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    document = dc.OutputDocument()
    for _ in range(30):
        document.append("answer", "abc\t" * 60 + "\n")
    with create_pipe_input() as pipe:
        view = ConsoleView(pt_input=pipe, pt_output=DummyOutput(), document=document)
        view.start()
        try:
            assert _wait_for(
                lambda: view._output_window is not None
                and view._output_window.render_info is not None
            )
            window = view._output_window
            view._output_buffer.cursor_position = 0
            assert _wait_for(lambda: window.vertical_scroll == 0)
            top = window.vertical_scroll
            pipe.send_text("\x1b[<0;1;2M")  # press on the second screen row
            assert _wait_for(lambda: view._output_buffer.cursor_position == 64)
            pipe.send_text("\x1b[<32;1;2M")  # drag within the interior row
            pipe.send_text("\x1b[<32;1;2M")
            import time as _time

            _time.sleep(0.8)  # past the repeat's initial delay
            assert view._output_control._edge_task is None
            assert window.vertical_scroll == top
            pipe.send_text("\x1b[<0;1;2m")
        finally:
            view.stop()


def test_view_resync_busy_after_suspend_clears_the_stale_flag():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            view.suspend()
            # The turn ended while the view was suspended, so no
            # status update reached it; on resume the reader
            # re-aligns the cached flag before submissions gate.
            view.start()
            assert _wait_for(lambda: view._app is not None and view.running)
            view.resync_busy(False)
            pipe.send_text("ordinary now\r")
            line = view.wait_line(abort=lambda: False)
            assert line == "ordinary now"
            # Idle path: no confirmation opened, no pending token.
            assert view._confirm_text is None
            assert view.last_pending_token is None
            # The reverse direction re-arms the confirmation gate.
            view.resync_busy(True)
            pipe.send_text("while busy\r")
            assert _wait_for(lambda: view._confirm_text == "while busy")
            pipe.send_text("n")
            assert view.wait_line(abort=lambda: False) == "while busy"
        finally:
            view.stop()


def test_view_batched_keys_after_a_confirmation_start_fresh():
    # Codex's repro: a confirmation answer and the next message in
    # one input batch.  The buffer must be reset synchronously when
    # the answer is processed — a deferred reset lets the batched
    # keys append to the answered message ("onesecond").
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text("one\rnsecond\rn")
            assert view.wait_line(abort=lambda: False) == "one"
            assert view.wait_line(abort=lambda: False) == "second"
            assert view._input_buffer.text == ""
        finally:
            view.stop()


def test_view_priority_line_reports_itself_and_requeues():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text("queued one\r")
            assert _wait_for(lambda: view._confirm_text == "queued one")
            pipe.send_text("n")
            assert _wait_for(lambda: view._confirm_text is None)
            pipe.send_text("chosen one\r")
            assert _wait_for(lambda: view._confirm_text == "chosen one")
            pipe.send_text("y")
            assert _wait_for(lambda: not view._priority.empty())
            line = view.wait_line(abort=lambda: False)
            assert line == "chosen one"
            # Interrupt-chosen lines carry no pending token, but
            # they report themselves as priority so a human_ask
            # takeover can preserve them by that flag instead.
            assert view.last_pending_token is None
            assert view.last_line_priority is True
            view.requeue_priority(line)
            assert view.wait_line(abort=lambda: False) == "chosen one"
            assert view.last_line_priority is True
            assert view.wait_line(abort=lambda: False) == "queued one"
            assert view.last_line_priority is False
            assert view.last_pending_token is not None
        finally:
            view.stop()


def test_view_priority_line_overtakes_a_requeued_held_line():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document)
        try:
            pipe.send_text(":status\r")
            held = view.wait_line(abort=lambda: False)
            held_token = view.last_pending_token
            assert held == ":status"
            assert held_token is not None
            # While the reader holds that line, the user submits a
            # message and chooses to interrupt for it.
            pipe.send_text("urgent\r")
            assert _wait_for(lambda: view._confirm_text == "urgent")
            pipe.send_text("y")
            assert _wait_for(lambda: view.take_priority_line() == "urgent")
            # The held line goes back to the front and is read
            # again ahead of anything queued later, token intact.
            view.requeue_front(held, held_token)
            pipe.send_text(":later\r")
            assert view.wait_line(abort=lambda: False) == ":status"
            assert view.last_pending_token is held_token
            assert view.wait_line(abort=lambda: False) == ":later"
        finally:
            view.stop()


def test_view_ctrl_c_at_confirmation_queues_instead_of_cancelling():
    from prompt_toolkit.input import create_pipe_input

    document = dc.OutputDocument()
    ctrl_c_calls: list[bool] = []
    with create_pipe_input() as pipe:
        view = _busy_view(pipe, document, on_ctrl_c=lambda: ctrl_c_calls.append(True))
        try:
            pipe.send_text("careful message\r")
            assert _wait_for(lambda: view._confirm_text == "careful message")
            pipe.send_text("\x03")
            assert view.wait_line(abort=lambda: False) == "careful message"
            assert view.last_pending_token is not None
            # Ctrl+C answered the question (queue); it did not fall
            # through to the turn-level Ctrl+C handler.
            assert ctrl_c_calls == []
        finally:
            view.stop()

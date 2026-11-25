"""Display worker tests: bitchat messages vs. an open toolkit prompt."""

from __future__ import annotations

import threading
import time

import pytest

from uagent.tools import pybitchat_shared as shared


def _start_toolkit_prompt():
    """Run a real PromptSession on pipe input in a background thread."""
    import io

    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit import PromptSession
    from prompt_toolkit.data_structures import Size
    from prompt_toolkit.input.defaults import create_pipe_input
    from prompt_toolkit.output.vt100 import Vt100_Output

    term_out = io.StringIO()
    output = Vt100_Output(term_out, lambda: Size(columns=80, rows=24))
    # Keep the context manager alive: dropping it closes the pipe and the
    # prompt reads EOF immediately.
    pipe_cm = create_pipe_input()
    pipe_input = pipe_cm.__enter__()
    session = PromptSession(input=pipe_input, output=output)
    session._test_pipe_cm = pipe_cm
    result: dict = {}

    def _run() -> None:
        try:
            result["text"] = session.prompt("User> ")
        except Exception as exc:  # noqa: BLE001 - surfaced by assertions
            result["error"] = exc

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline:
        app = session.app
        if app is not None and app.is_running and "User>" in term_out.getvalue():
            break
        time.sleep(0.02)
    else:
        raise AssertionError("toolkit prompt did not start")
    return pipe_input, session, term_out, result, thread


def _wait_for_rendered(term_out, mark: int, *fragments: str) -> str:
    deadline = time.time() + 5
    rendered = ""
    while time.time() < deadline:
        rendered = term_out.getvalue()[mark:]
        if all(fragment in rendered for fragment in fragments):
            break
        time.sleep(0.02)
    return rendered


def _wait_for_output(capsys, fragment: str) -> str:
    """Accumulate captured stdout until ``fragment`` shows up."""
    seen = ""
    deadline = time.time() + 5
    while time.time() < deadline:
        seen += capsys.readouterr().out
        if fragment in seen:
            break
        time.sleep(0.02)
    return seen


def _patch_core(monkeypatch, **attrs):
    from uagent import core

    for name, value in attrs.items():
        monkeypatch.setattr(core, name, value, raising=False)
    return core


def test_display_worker_prints_above_an_open_toolkit_prompt(capsys, monkeypatch):
    pipe_input, session, term_out, result, thread = _start_toolkit_prompt()
    try:
        pipe_input.send_text("draft")
        _wait_for_rendered(term_out, 0, "draft")

        deltas: list[str] = []
        core = _patch_core(
            monkeypatch,
            _stream_line_open=False,
            _reasoning_stream_open=False,
            _prompt_line_open=True,
            prompt_needs_redraw=False,
            _cli_prompt_toolkit_active=True,
            _cli_prompt_app=session.app,
            print_stream_delta=deltas.append,
            print_stream_delta_locked=deltas.append,
        )

        mark = len(term_out.getvalue())
        shared._notify_display("[bitchat] hello from peer")

        # The message was printed (above the prompt), not written into the
        # line being edited via the manual stream path.
        seen = _wait_for_output(capsys, "[bitchat] hello from peer")
        assert "[bitchat] hello from peer" in seen
        assert deltas == []
        # The prompt redraws below the message with the edit buffer intact.
        redrawn = _wait_for_rendered(term_out, mark, "User>", "draft")
        assert "User>" in redrawn
        assert "draft" in redrawn
        # The prompt still owns the line; no manual redraw was requested.
        assert core._prompt_line_open is True
        assert core.prompt_needs_redraw is False

        pipe_input.send_text("\r")
        thread.join(timeout=5)
        assert result.get("text") == "draft"
    finally:
        pipe_input.close()


def test_display_worker_manual_path_without_toolkit_prompt(monkeypatch):
    deltas: list[str] = []
    core = _patch_core(
        monkeypatch,
        _stream_line_open=False,
        _reasoning_stream_open=False,
        _prompt_line_open=True,
        prompt_needs_redraw=False,
        _cli_prompt_toolkit_active=False,
        _cli_prompt_app=None,
        print_stream_delta_locked=deltas.append,
    )

    shared._notify_display("[bitchat] manual path message")

    deadline = time.time() + 5
    while time.time() < deadline:
        if any("manual path message" in delta for delta in deltas):
            break
        time.sleep(0.02)
    # Existing manual behaviour: close the prompt line, print through the
    # stream, and ask the input loop to redraw the prompt.
    assert deltas == ["\n", "[bitchat] manual path message\n"]
    assert core._prompt_line_open is False
    assert core.prompt_needs_redraw is True

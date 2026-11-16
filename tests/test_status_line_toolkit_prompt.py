"""Regression: [STATE] must yield a prompt_toolkit prompt, not erase it.

When an injected round starts while a prompt_toolkit prompt is on
screen, print_status_line used to erase the prompt line by hand while
the application was still running; the application then redrew the
prompt over the spinner frame, leaving a merged line in the
scrollback. The status printer now asks the application to exit and
waits for the input loop to release the line first.
"""

from __future__ import annotations

import io
import sys
import threading
import time

import uagent.core as core


class _FakeApp:
    def __init__(self, *, releases: bool) -> None:
        self.is_running = True
        self.exit_calls = 0
        self._releases = releases

    def exit(self, result=None) -> None:
        self.exit_calls += 1
        if self._releases:

            def _release() -> None:
                time.sleep(0.02)
                core._prompt_line_open = False

            threading.Thread(target=_release, daemon=True).start()


def _setup(monkeypatch, app) -> tuple[io.StringIO, io.StringIO]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(core, "IS_GUI", True)
    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(core, "status_busy", True)
    monkeypatch.setattr(core, "status_label", "LLM")
    monkeypatch.setattr(core, "_stream_line_open", False)
    monkeypatch.setattr(core, "_reasoning_stream_open", False)
    monkeypatch.setattr(core, "_prompt_line_open", True)
    monkeypatch.setattr(core, "_cli_prompt_toolkit_active", True, raising=False)
    monkeypatch.setattr(core, "_cli_prompt_app", app, raising=False)
    return stdout, stderr


def test_status_line_exits_toolkit_prompt_instead_of_erasing(monkeypatch):
    app = _FakeApp(releases=True)
    stdout, stderr = _setup(monkeypatch, app)

    core.print_status_line()

    assert app.exit_calls == 1
    # The application released the line, so the manual erase (carriage
    # return plus a run of spaces) must not appear in the output.
    assert " " * 120 not in stdout.getvalue()
    assert "[STATE] BUSY [LLM]" in stderr.getvalue()


def test_status_line_falls_back_to_manual_erase_when_prompt_stays(monkeypatch):
    app = _FakeApp(releases=False)
    stdout, stderr = _setup(monkeypatch, app)

    core.print_status_line()

    assert app.exit_calls == 1
    assert " " * 120 in stdout.getvalue()
    assert "[STATE] BUSY [LLM]" in stderr.getvalue()

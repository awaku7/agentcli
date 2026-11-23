"""Busy status updates must preserve an active prompt_toolkit prompt."""

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


def test_status_line_preserves_a_live_toolkit_prompt(monkeypatch):
    app = _FakeApp(releases=True)
    stdout, stderr = _setup(monkeypatch, app)

    core.print_status_line()

    assert app.exit_calls == 0
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""
    assert core._prompt_line_open


def test_status_line_does_not_erase_prompt_when_toolkit_keeps_running(monkeypatch):
    app = _FakeApp(releases=False)
    stdout, stderr = _setup(monkeypatch, app)

    core.print_status_line()

    assert app.exit_calls == 0
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""
    assert core._prompt_line_open

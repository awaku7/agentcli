"""Regression: [STATE] must not be injected mid-stream text."""

from __future__ import annotations

import io
import sys

import uagent.core as core
from uagent import web as webmod


def test_print_status_line_force_closes_open_stream(monkeypatch):
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(core, "IS_GUI", True)
    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(core, "status_busy", True)
    monkeypatch.setattr(core, "status_label", "tool:parallel")
    monkeypatch.setattr(core, "_stream_line_open", True)

    t = {"v": 0.0}

    def fake_time():
        return t["v"]

    def fake_sleep(dt):
        t["v"] += float(dt)

    monkeypatch.setattr(core.time, "time", fake_time)
    monkeypatch.setattr(core.time, "sleep", fake_sleep)

    core.print_status_line()

    out = stdout.getvalue()
    err = stderr.getvalue()
    assert out.endswith(chr(10))
    assert "[STATE] BUSY [tool:parallel]" in err
    assert not core._stream_line_open


def test_print_status_line_waits_for_natural_newline(monkeypatch):
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(core, "IS_GUI", True)
    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(core, "status_busy", True)
    monkeypatch.setattr(core, "status_label", "LLM")
    monkeypatch.setattr(core, "_stream_line_open", True)

    t = {"v": 0.0}

    def fake_time():
        return t["v"]

    def fake_sleep(dt):
        t["v"] += float(dt)
        if t["v"] >= 0.05:
            with core.print_lock:
                core._stream_line_open = False

    monkeypatch.setattr(core.time, "time", fake_time)
    monkeypatch.setattr(core.time, "sleep", fake_sleep)

    core.print_status_line()

    assert "[STATE] BUSY [LLM]" in stderr.getvalue()
    assert stdout.getvalue() == ""
    assert not core._stream_line_open


def test_set_status_uses_reasoning_label_for_generic_llm(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "auto")
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.setattr(core, "last_reasoning_label", "")
    monkeypatch.setattr(core, "print_status_line", lambda: None)

    core.set_status(True, "LLM")

    assert core.status_label == "LLM:auto"


def test_web_room_status_uses_reasoning_label(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "high")
    room = webmod.WebRoom("test-room")

    room.set_status(True, "LLM")

    assert room.status["label"] == "LLM:high"


def test_set_status_keeps_generic_llm_when_reasoning_is_off(monkeypatch):
    monkeypatch.setenv("UAGENT_REASONING", "off")
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.setattr(core, "last_reasoning_label", "")
    monkeypatch.setattr(core, "print_status_line", lambda: None)

    core.set_status(True, "LLM")

    assert core.status_label == "LLM"


def test_print_stream_delta_tracks_open_line(monkeypatch):
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(core, "_stream_line_open", False)

    core.print_stream_delta("hello")
    assert core._stream_line_open is True
    core.print_stream_delta(" world" + chr(10))
    assert core._stream_line_open is False
    assert stdout.getvalue() == "hello world" + chr(10)


def test_strip_state_markers_web():
    assert webmod._strip_state_markers("[STATE] BUSY [tool:parallel]") == ""
    assert (
        webmod._strip_state_markers("hello [STATE] BUSY [LLM] world") == "hello  world"
    )
    assert webmod._strip_state_markers("plain text") == "plain text"


def test_print_status_line_windows_never_emits_ansi(monkeypatch):
    """Windows path must not write ANSI ESC (prevents ?[32m IDLE leaks)."""
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(core, "IS_GUI", False)
    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(core, "_stream_line_open", False)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("UAGENT_NO_COLOR", raising=False)
    monkeypatch.delenv("UAGENT_STATUS_COLOR", raising=False)
    monkeypatch.setattr(stderr, "isatty", lambda: True)
    monkeypatch.setattr(core.os, "name", "nt")

    # No real console in pytest -> Win32 path falls back to plain text.
    core.print_status_line()
    err = stderr.getvalue()
    assert err == "[STATE] IDLE" + chr(13) + chr(10)
    assert chr(27) not in err
    assert "[32m" not in err
    assert "[0m" not in err
    assert "?[" not in err


def test_print_status_line_posix_ansi(monkeypatch):
    """Non-Windows TTY uses ANSI colors."""
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(core, "IS_GUI", False)
    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(core, "_stream_line_open", False)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("UAGENT_NO_COLOR", raising=False)
    monkeypatch.delenv("UAGENT_STATUS_COLOR", raising=False)
    monkeypatch.setattr(stderr, "isatty", lambda: True)
    monkeypatch.setattr(core.os, "name", "posix")

    core.print_status_line()
    err = stderr.getvalue()
    assert err == chr(27) + "[32m[STATE] IDLE" + chr(27) + "[0m" + chr(10)


def test_print_status_line_color_opt_out(monkeypatch):
    """UAGENT_STATUS_COLOR=0 disables colors everywhere."""
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(core, "IS_GUI", False)
    monkeypatch.setattr(core, "_is_web", False, raising=False)
    monkeypatch.setattr(core, "human_ask_active", False)
    monkeypatch.setattr(core, "_stream_line_open", False)
    monkeypatch.setattr(core, "status_busy", False)
    monkeypatch.setattr(core, "status_label", "")
    monkeypatch.setenv("UAGENT_STATUS_COLOR", "0")
    monkeypatch.setattr(stderr, "isatty", lambda: True)
    monkeypatch.setattr(core.os, "name", "posix")

    core.print_status_line()
    err = stderr.getvalue()
    assert err == "[STATE] IDLE" + chr(10)
    assert chr(27) not in err

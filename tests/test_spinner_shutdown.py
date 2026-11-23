from __future__ import annotations

from threading import Event, Thread

from uagent.runtime import spinner


def test_stop_quietly_does_not_leave_done_line(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def record_stop(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(spinner, "stop", record_stop)

    spinner.stop_quietly(clear=False)

    assert calls == [{"clear": False, "keep_last_line": False}]


def test_paused_clears_spinner_without_leaving_done_line(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def record_stop(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(spinner, "stop", record_stop)

    with spinner.paused():
        pass

    assert calls == [{"clear": True, "keep_last_line": False}]


def test_stop_clears_frame_drawn_while_shutdown_is_requested(monkeypatch) -> None:
    frame_started = Event()
    release_frame = Event()
    done_lines: list[tuple[str, float | None]] = []

    spinner.stop(keep_last_line=False)
    monkeypatch.setattr(spinner, "spinner_enabled", lambda: True)
    monkeypatch.setattr(spinner, "_ok_to_draw", lambda: True)
    monkeypatch.setattr(spinner, "_frames", lambda: ("*",))
    monkeypatch.setattr(spinner, "_done_line_kept", lambda _label="": True)
    monkeypatch.setattr(
        spinner,
        "_write_done_line",
        lambda label, elapsed: done_lines.append((label, elapsed)),
    )

    def hold_frame(_text: str, _pad: int) -> None:
        frame_started.set()
        assert release_frame.wait(timeout=2)

    monkeypatch.setattr(spinner, "_write_spinner_frame", hold_frame)
    spinner.start(interval=0.001)
    assert frame_started.wait(timeout=1)

    stop_started = Event()

    def stop_spinner() -> None:
        stop_started.set()
        spinner.stop()

    stopper = Thread(target=stop_spinner)
    stopper.start()
    assert stop_started.wait(timeout=1)

    # On the old ordering, stop snapshots _DREW before the blocked frame
    # finishes. On the synchronized path, stop waits for the frame lock.
    spinner._stop.wait(timeout=0.05)
    release_frame.set()
    stopper.join(timeout=2)

    assert not stopper.is_alive()
    assert len(done_lines) == 1
    assert spinner._DREW is False
    assert spinner._thread is None


def test_command_pending_spinner_does_not_leave_done_line_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("UAGENT_SPINNER_DONE", raising=False)

    assert spinner._done_line_kept("command_pending") is False
    assert spinner._done_line_kept("LLM") is True


def test_spinner_done_setting_can_override_command_default(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_SPINNER_DONE", "on")
    assert spinner._done_line_kept("command_pending") is True

    monkeypatch.setenv("UAGENT_SPINNER_DONE", "off")
    assert spinner._done_line_kept("LLM") is False

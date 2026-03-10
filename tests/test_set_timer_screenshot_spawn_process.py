from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_set_timer_rejects_non_integer_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import set_timer_tool

    cb = SimpleNamespace(event_queue=object(), set_status=None)
    monkeypatch.setattr(set_timer_tool, "get_callbacks", lambda: cb)

    out = set_timer_tool.run_tool({"seconds": "abc"})
    assert out.startswith("[set_timer error]")
    assert "'abc'" in out


def test_set_timer_rejects_negative_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import set_timer_tool

    cb = SimpleNamespace(event_queue=object(), set_status=None)
    monkeypatch.setattr(set_timer_tool, "get_callbacks", lambda: cb)

    out = set_timer_tool.run_tool({"seconds": -1})
    assert out.startswith("[set_timer error]")
    assert "-1" in out


def test_set_timer_errors_when_event_queue_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import set_timer_tool

    cb = SimpleNamespace(event_queue=None, set_status=None)
    monkeypatch.setattr(set_timer_tool, "get_callbacks", lambda: cb)

    out = set_timer_tool.run_tool({"seconds": 0})
    assert out.startswith("[set_timer error]")


def test_set_timer_enqueues_event_without_real_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import set_timer_tool

    events: list[dict] = []
    status_calls: list[tuple[bool, str]] = []

    class DummyQueue:
        def put(self, item: dict) -> None:
            events.append(item)

    class DummyThread:
        def __init__(self, target, daemon: bool = True):
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            self._target()

    cb = SimpleNamespace(
        event_queue=DummyQueue(),
        set_status=lambda busy, label: status_calls.append((busy, label)),
    )

    monkeypatch.setattr(set_timer_tool, "get_callbacks", lambda: cb)
    monkeypatch.setattr(set_timer_tool.time, "sleep", lambda _s: None)
    monkeypatch.setattr(set_timer_tool.threading, "Thread", DummyThread)

    out = set_timer_tool.run_tool(
        {"seconds": 1, "message": "done", "on_timeout_prompt": "auto"}
    )

    assert out.startswith("[set_timer]")
    assert "on_timeout_prompt='auto'" in out
    assert events == [{"kind": "timer", "text": "auto"}]
    assert status_calls == [(True, "timer_pending")]


def test_screenshot_errors_when_pyautogui_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import screenshot_tool

    monkeypatch.setattr(screenshot_tool, "pyautogui", None)
    out = screenshot_tool.run_tool({})

    assert out.startswith("[screenshot error]")


def test_screenshot_errors_when_window_targeting_without_pygetwindow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import screenshot_tool

    fake_pyautogui = SimpleNamespace(screenshot=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(screenshot_tool, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(screenshot_tool, "pygetwindow", None)

    out = screenshot_tool.run_tool({"window_title": "notepad"})
    assert out.startswith("[screenshot error]")


def test_screenshot_captures_desktop_with_given_path(
    monkeypatch: pytest.MonkeyPatch, repo_tmp_path
) -> None:
    from uagent.tools import screenshot_tool

    calls: list[tuple[str, object]] = []

    def fake_screenshot(path: str, region=None) -> None:
        calls.append((path, region))

    fake_pyautogui = SimpleNamespace(screenshot=fake_screenshot)
    monkeypatch.setattr(screenshot_tool, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(screenshot_tool.time, "sleep", lambda _s: None)

    out_file = repo_tmp_path / "cap.png"
    out = screenshot_tool.run_tool({"file_path": str(out_file), "delay": 0})

    assert out.startswith("[screenshot]")
    assert str(out_file) in out
    assert calls == [(str(out_file), None)]


def test_screenshot_window_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import screenshot_tool

    fake_pyautogui = SimpleNamespace(screenshot=lambda *_args, **_kwargs: None)
    fake_pygetwindow = SimpleNamespace(getWindowsWithTitle=lambda _title: [])

    monkeypatch.setattr(screenshot_tool, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(screenshot_tool, "pygetwindow", fake_pygetwindow)

    out = screenshot_tool.run_tool({"window_title": "missing", "delay": 0})
    assert out.startswith("[screenshot error]")
    assert "missing" in out


def test_screenshot_window_capture_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import screenshot_tool

    calls: list[tuple[str, object]] = []

    class FakeWindow:
        left = 10
        top = 20
        width = 300
        height = 400
        isMinimized = True

        def __init__(self) -> None:
            self.restored = False
            self.activated = False
            self.closed = False

        def restore(self) -> None:
            self.restored = True

        def activate(self) -> None:
            self.activated = True

        def close(self) -> None:
            self.closed = True

    win = FakeWindow()

    def fake_screenshot(path: str, region=None) -> None:
        calls.append((path, region))

    fake_pyautogui = SimpleNamespace(screenshot=fake_screenshot)
    fake_pygetwindow = SimpleNamespace(getWindowsWithTitle=lambda _title: [win])

    monkeypatch.setattr(screenshot_tool, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(screenshot_tool, "pygetwindow", fake_pygetwindow)
    monkeypatch.setattr(screenshot_tool.time, "sleep", lambda _s: None)

    out = screenshot_tool.run_tool(
        {"window_title": "demo", "delay": 0, "close_window": True, "file_path": "x.png"}
    )

    assert out.startswith("[screenshot]")
    assert "x.png" in out
    assert calls == [("x.png", (10, 20, 300, 400))]
    assert win.restored is True
    assert win.activated is True
    assert win.closed is True


def test_spawn_process_rejects_empty_command() -> None:
    from uagent.tools import spawn_process_tool

    out = spawn_process_tool.run_tool({"command": "   "})
    assert out.startswith("[spawn_process error]")


def test_spawn_process_windows_start_without_target_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import spawn_process_tool

    monkeypatch.setattr(spawn_process_tool.os, "name", "nt", raising=False)
    out = spawn_process_tool.run_tool({"command": 'start ""'})
    assert out.startswith("[spawn_process error]")


def test_spawn_process_nt_executes_via_cmd_exe(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import spawn_process_tool

    calls: list[tuple[tuple, dict]] = []

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(spawn_process_tool.os, "name", "nt", raising=False)
    monkeypatch.setattr(spawn_process_tool.subprocess, "Popen", fake_popen)

    out = spawn_process_tool.run_tool({"command": 'start "" https://example.com'})

    assert "cmd.exe /c start" in out
    assert calls
    args, kwargs = calls[0]
    assert args[0].startswith("cmd.exe /c start")
    assert kwargs["shell"] is False


def test_spawn_process_posix_executes_with_shell_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import spawn_process_tool

    calls: list[tuple[tuple, dict]] = []

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(spawn_process_tool.os, "name", "posix", raising=False)
    monkeypatch.setattr(spawn_process_tool.subprocess, "Popen", fake_popen)

    out = spawn_process_tool.run_tool({"command": "xdg-open https://example.com"})

    assert "xdg-open https://example.com" in out
    args, kwargs = calls[0]
    assert args[0] == "xdg-open https://example.com"
    assert kwargs["shell"] is True


def test_spawn_process_returns_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import spawn_process_tool

    def fake_popen(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(spawn_process_tool.os, "name", "posix", raising=False)
    monkeypatch.setattr(spawn_process_tool.subprocess, "Popen", fake_popen)

    out = spawn_process_tool.run_tool({"command": "echo hi"})
    assert out.startswith("[spawn_process error]")
    assert "RuntimeError: boom" in out

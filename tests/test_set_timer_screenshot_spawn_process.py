from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _set_timer_module(monkeypatch: pytest.MonkeyPatch):
    from uagent.tools import set_timer_tool

    monkeypatch.setattr(
        set_timer_tool,
        "_",
        lambda key, default=None: default if default is not None else key,
    )
    return set_timer_tool


def test_set_timer_rejects_non_integer_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    set_timer_tool = _set_timer_module(monkeypatch)

    out = set_timer_tool.run_tool({"seconds": "abc"})
    assert out.startswith("[set_timer error]")
    assert "abc" in out


def test_set_timer_rejects_negative_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    set_timer_tool = _set_timer_module(monkeypatch)

    out = set_timer_tool.run_tool({"seconds": -1})
    assert out.startswith("[set_timer error]")
    assert "-1" in out


def test_set_timer_creates_persistent_schedule_with_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_timer_tool = _set_timer_module(monkeypatch)

    fixed_now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    captured: dict[str, object] = {}

    class DummyStore:
        def add_item(self, item):
            captured["item"] = item
            return item

    store = DummyStore()
    monkeypatch.setattr(set_timer_tool, "SchedulerStore", lambda: store)
    monkeypatch.setattr(set_timer_tool, "utc_now", lambda: fixed_now)

    out = set_timer_tool.run_tool(
        {"seconds": 1, "message": "done", "on_timeout_prompt": "auto"}
    )

    item = captured["item"]
    assert out.startswith("[set_timer]")
    assert "auto" in out
    assert item.message == "done"
    assert item.llm_prompt == "auto"
    assert item.enabled is True
    assert item.interval_sec == 0
    assert item.type == set_timer_tool.SCHEDULE_TYPE_ONCE
    assert item.at == set_timer_tool.format_iso_datetime(
        fixed_now + timedelta(seconds=1)
    )


def test_set_timer_defaults_message_and_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    set_timer_tool = _set_timer_module(monkeypatch)

    fixed_now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    captured: dict[str, object] = {}

    class DummyStore:
        def add_item(self, item):
            captured["item"] = item
            return item

    store = DummyStore()
    monkeypatch.setattr(set_timer_tool, "SchedulerStore", lambda: store)
    monkeypatch.setattr(set_timer_tool, "utc_now", lambda: fixed_now)

    out = set_timer_tool.run_tool({"seconds": 0})

    item = captured["item"]
    assert out.startswith("[set_timer]")
    assert item.message == "Timer finished"
    assert item.llm_prompt == ""
    assert item.at == set_timer_tool.format_iso_datetime(fixed_now)


def test_screenshot_errors_when_pyautogui_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import screenshot_tool

    monkeypatch.setattr(screenshot_tool, "pyautogui", None)
    out = screenshot_tool.run_tool({})

    import json
    obj = json.loads(out)
    assert obj.get("ok") is False
    assert "[screenshot error]" in obj.get("message", "") or "pyautogui" in obj.get("message", "")


def test_screenshot_errors_when_window_targeting_without_pygetwindow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools import screenshot_tool

    fake_pyautogui = SimpleNamespace(screenshot=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(screenshot_tool, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(screenshot_tool, "pygetwindow", None)

    out = screenshot_tool.run_tool({"window_title": "notepad"})
    import json
    obj = json.loads(out)
    assert obj.get("ok") is False
    assert "[screenshot error]" in obj.get("message", "") or "pygetwindow" in obj.get("message", "")


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

    import json
    obj = json.loads(out)
    assert obj.get("ok") is True
    assert "[screenshot]" in obj.get("message", "")
    assert str(out_file) in obj.get("message", "")
    assert calls == [(str(out_file), None)]


def test_screenshot_window_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools import screenshot_tool

    fake_pyautogui = SimpleNamespace(screenshot=lambda *_args, **_kwargs: None)
    fake_pygetwindow = SimpleNamespace(getWindowsWithTitle=lambda _title: [])

    monkeypatch.setattr(screenshot_tool, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(screenshot_tool, "pygetwindow", fake_pygetwindow)

    out = screenshot_tool.run_tool({"window_title": "missing", "delay": 0})
    import json
    obj = json.loads(out)
    assert obj.get("ok") is False
    assert "[screenshot error]" in obj.get("message", "") or "missing" in obj.get("message", "")


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

    import json
    obj = json.loads(out)
    assert obj.get("ok") is True
    assert "[screenshot]" in obj.get("message", "")
    assert "x.png" in obj.get("message", "")
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

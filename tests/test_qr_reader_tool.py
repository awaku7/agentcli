from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from uagent.tools import qr_reader_tool


def test_reader_tool_launches_standalone_window(monkeypatch) -> None:
    calls = []
    process = SimpleNamespace(
        pid=4321,
        poll=lambda: None,
        returncode=0,
        communicate=lambda: ('{"text":"decoded QR payload"}', None),
    )

    monkeypatch.setattr(qr_reader_tool, "_ensure_dependencies", lambda: True)
    monkeypatch.setattr(qr_reader_tool, "_tkinter_available", lambda: True)
    monkeypatch.setattr(
        qr_reader_tool.subprocess,
        "Popen",
        lambda command, **kwargs: calls.append((command, kwargs)) or process,
    )
    monkeypatch.setattr(qr_reader_tool, "_READER_PROCESS", None)

    result = json.loads(qr_reader_tool.run_tool({}))
    assert result["ok"] is True
    assert result["data"]["text"] == "decoded QR payload"
    assert result["data"]["untrusted"] is True
    assert len(calls) == 1
    command, options = calls[0]
    assert command[0] == qr_reader_tool.sys.executable
    assert Path(command[1]).name == "qr_reader_ui.py"
    assert options["stdin"] is qr_reader_tool.subprocess.DEVNULL
    assert options["stdout"] is qr_reader_tool.subprocess.PIPE
    assert options["text"] is True


def test_reader_tool_does_not_open_duplicate_window(monkeypatch) -> None:
    process = SimpleNamespace(pid=1234, poll=lambda: None)
    monkeypatch.setattr(qr_reader_tool, "_READER_PROCESS", process)
    monkeypatch.setattr(
        qr_reader_tool.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("duplicate launch")
        ),
    )

    result = json.loads(qr_reader_tool.run_tool({}))
    assert result["data"]["already_open"] is True

from __future__ import annotations

import importlib
import sys
import types

from uagent import core
from uagent.runtime.observability.content_runtime import capture_logged_message


def _load_worker(monkeypatch):
    qtcore = types.ModuleType("PySide6.QtCore")

    class QObject:
        pass

    class Signal:
        def __init__(self, *_args, **_kwargs):
            pass

        def emit(self, *_args, **_kwargs):
            return None

    def Slot(*_args, **_kwargs):
        def decorator(fn):
            return fn

        return decorator

    qtcore.QObject = QObject
    qtcore.Signal = Signal
    qtcore.Slot = Slot
    pyside6 = types.ModuleType("PySide6")
    pyside6.QtCore = qtcore
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    sys.modules.pop("uagent.scheckgui_impl.worker", None)
    return importlib.import_module("uagent.scheckgui_impl.worker")


def test_gui_attachment_log_envelope_preserves_capture_denial(monkeypatch) -> None:
    worker = _load_worker(monkeypatch)
    logged: list[dict[str, object]] = []
    monkeypatch.setattr(core, "log_message", logged.append)

    message = {
        "role": "user",
        "content": "[Attached File] report.txt (C:/private/report.txt)",
    }
    worker._log_gui_user_message(message, attachment_derived=True)

    assert logged == [
        {
            "role": "user",
            "content": "[Attached File] report.txt (C:/private/report.txt)",
            "attachments": True,
        }
    ]
    assert capture_logged_message(logged[0]) is False
    assert "attachments" not in message


def test_gui_plain_log_envelope_is_unchanged(monkeypatch) -> None:
    worker = _load_worker(monkeypatch)
    logged: list[dict[str, object]] = []
    monkeypatch.setattr(core, "log_message", logged.append)
    message = {"role": "user", "content": "plain text"}

    worker._log_gui_user_message(message, attachment_derived=False)

    assert logged == [message]
    assert logged[0] is message

"""GUI worker callback wiring.

The GUI builds its own ToolCallbacks instead of using the shared
``init_tools_callbacks`` setup, so every human_ask setter the tools
need must be wired there too. In particular, ``human_ask`` publishes
its question only through ``human_ask_set_message``; without it
``core.human_ask_message`` stays empty and ask forwarding (bitchat
and the Nostr remote) never sees the question.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

try:
    import PySide6  # noqa: F401
except ImportError:
    # The test venv has no Qt; stub just enough for the worker module
    # to import. The test never constructs a real QObject.
    pyside = types.ModuleType("PySide6")
    qtcore = types.ModuleType("PySide6.QtCore")

    class _Signal:
        def __init__(self, *a, **k):
            pass

        def emit(self, *a, **k):
            pass

    class _QObject:
        def __init__(self, *a, **k):
            pass

    qtcore.Signal = _Signal
    qtcore.QObject = _QObject
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    pyside.QtCore = qtcore
    sys.modules.setdefault("PySide6", pyside)
    sys.modules.setdefault("PySide6.QtCore", qtcore)

from uagent import core
from uagent.scheckgui_impl.worker import ScheckWorker


def test_gui_callbacks_wire_human_ask_message(monkeypatch) -> None:
    captured: dict[str, object] = {}
    worker = SimpleNamespace(
        tools=SimpleNamespace(init_callbacks=lambda cb: captured.setdefault("cb", cb)),
        sig_image_event=SimpleNamespace(emit=lambda value: None),
    )
    ScheckWorker._init_callbacks(worker)
    cb = captured["cb"]
    assert cb.human_ask_set_message is not None
    monkeypatch.setattr(core, "human_ask_message", "", raising=False)
    cb.human_ask_set_message("Which file?")
    assert core.human_ask_message == "Which file?"

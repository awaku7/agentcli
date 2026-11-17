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

from uagent import core


def _load_gui_worker():
    """Import the GUI worker module, stubbing PySide6 when Qt is absent.

    The stub is installed only for the duration of the import and is
    removed again by the returned cleanup, so other tests in the same
    process still see Qt as unavailable.
    """
    try:
        import PySide6  # noqa: F401
    except ImportError:
        pass
    else:
        from uagent.scheckgui_impl import worker

        return worker, lambda: None

    def _drop(prefixes: tuple[str, ...]) -> dict[str, object]:
        saved: dict[str, object] = {}
        for name in list(sys.modules):
            if any(name == p or name.startswith(p + ".") for p in prefixes):
                saved[name] = sys.modules.pop(name)
        return saved

    prefixes = ("PySide6", "uagent.scheckgui_impl.worker")
    saved = _drop(prefixes)

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
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore
    try:
        from uagent.scheckgui_impl import worker
    except BaseException:
        _drop(prefixes)
        sys.modules.update(saved)
        raise

    def cleanup() -> None:
        _drop(prefixes)
        sys.modules.update(saved)

    return worker, cleanup


def test_gui_callbacks_wire_human_ask_message(monkeypatch) -> None:
    worker_module, cleanup = _load_gui_worker()
    captured: dict[str, object] = {}
    worker = SimpleNamespace(
        tools=SimpleNamespace(init_callbacks=lambda cb: captured.setdefault("cb", cb)),
        sig_image_event=SimpleNamespace(emit=lambda value: None),
    )
    try:
        worker_module.ScheckWorker._init_callbacks(worker)
    finally:
        cleanup()
    cb = captured["cb"]
    assert cb.human_ask_set_message is not None
    monkeypatch.setattr(core, "human_ask_message", "", raising=False)
    cb.human_ask_set_message("Which file?")
    assert core.human_ask_message == "Which file?"

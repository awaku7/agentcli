from __future__ import annotations

from types import SimpleNamespace

from uagent.tools import system_reload_tool


def test_system_reload_preserves_confirmation_callback(monkeypatch) -> None:
    def callback(*_args):
        return True

    fake_package = SimpleNamespace(
        _INITIALIZED=True,
        _DYNAMIC_COMMANDS={"stale": object()},
        _confirmation_callback=callback,
        _load_plugins=lambda: None,
    )
    fake_package.get_confirmation_callback = lambda: fake_package._confirmation_callback
    fake_package.set_confirmation_callback = lambda value: setattr(
        fake_package, "_confirmation_callback", value
    )

    def fake_reload(module):
        module._confirmation_callback = None
        return module

    monkeypatch.setattr(system_reload_tool, "__package__", "fake.tools")
    monkeypatch.setitem(system_reload_tool.sys.modules, "fake.tools", fake_package)
    monkeypatch.setattr(system_reload_tool.importlib, "reload", fake_reload)
    monkeypatch.setattr(system_reload_tool, "_stop_running_backgrounds", lambda: [])
    monkeypatch.setattr(system_reload_tool, "_restore_runtime_boundaries", lambda: None)

    result = system_reload_tool.run_tool({})

    assert result.startswith("System reload successful.")
    assert fake_package.get_confirmation_callback() is callback

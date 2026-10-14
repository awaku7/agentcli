from __future__ import annotations

from uagent import hooks_engine
from uagent.web_impl import init
from uagent.web_impl.rooms import web_manager


def test_remote_web_stop_hook_cannot_run_host_command(monkeypatch):
    calls = []
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)
    monkeypatch.setattr(web_manager, "sandbox_enabled", False, raising=False)
    monkeypatch.setattr(
        hooks_engine,
        "load_hooks_registry",
        lambda _path=None: {
            "Stop": [{"type": "command", "command": "echo stop-hook-must-not-run"}]
        },
    )
    monkeypatch.setattr(
        hooks_engine.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    init._fire_web_lifecycle_hook("Stop")

    assert calls == []


def test_local_trusted_web_stop_hook_uses_local_profile(monkeypatch):
    calls = []
    monkeypatch.setattr(
        web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", False, raising=False)
    monkeypatch.setattr(
        hooks_engine,
        "load_hooks_registry",
        lambda _path=None: {
            "Stop": [{"type": "command", "command": "echo trusted-stop-hook"}]
        },
    )

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(hooks_engine.subprocess, "run", fake_run)

    init._fire_web_lifecycle_hook("Stop")

    assert len(calls) == 1

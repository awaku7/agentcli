from __future__ import annotations

import pytest

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


@pytest.mark.parametrize("event_name", ["SessionStart", "Stop"])
def test_local_web_lifecycle_hooks_are_blocked_when_sandbox_enabled(
    monkeypatch, event_name
):
    calls = []
    monkeypatch.setattr(
        web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", True, raising=False)
    monkeypatch.setattr(
        hooks_engine,
        "load_hooks_registry",
        lambda _path=None: {
            event_name: [
                {"type": "command", "command": "echo sandboxed-hook-must-not-run"}
            ]
        },
    )
    monkeypatch.setattr(
        hooks_engine.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    init._fire_web_lifecycle_hook(event_name)

    assert calls == []


def test_local_web_sandbox_opt_in_initializes_the_verified_backend(monkeypatch):
    import argparse

    from uagent.runtime import mxc_backend

    manager = object()
    installed = []
    monkeypatch.setattr(mxc_backend, "mxc_sdk_is_installed", lambda: True)
    monkeypatch.setattr(
        mxc_backend.MxcSessionManager,
        "initialize",
        classmethod(lambda cls, *, allow_install: (manager, {"sdk": "test"})),
    )
    monkeypatch.setattr(mxc_backend, "install_session_manager", installed.append)
    monkeypatch.setattr(mxc_backend, "describe_probe", lambda _report: "probe-ok")

    result = init._initialize_local_web_sandbox(
        argparse.ArgumentParser(), sandbox_mode="auto"
    )

    assert result is manager
    assert installed == [manager]


def test_local_web_sandbox_fails_startup_if_backend_is_not_ready():
    import argparse

    with pytest.raises(SystemExit) as error:
        init._validate_web_sandbox_startup(
            argparse.ArgumentParser(),
            trusted_local=True,
            sandbox_enabled=True,
            backend_ready=False,
        )
    assert error.value.code == 2


def test_remote_web_sandbox_opt_in_can_start_toolless():
    import argparse

    # Remote tools remain broker-denied; this PoC backend is local-only.
    init._validate_web_sandbox_startup(
        argparse.ArgumentParser(),
        trusted_local=False,
        sandbox_enabled=True,
        backend_ready=False,
    )


def test_local_web_user_prompt_hook_is_blocked_when_sandbox_enabled(monkeypatch):
    from uagent.runtime.execution_broker import SecurityProfile, execution_profile

    calls = []
    monkeypatch.setattr(
        hooks_engine.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    hooks = {
        "UserPromptSubmit": [
            {"type": "command", "command": "echo sandboxed-prompt-hook-must-not-run"}
        ]
    }

    with execution_profile(SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True):
        results = hooks_engine.fire_user_prompt_submit("hello", hooks=hooks)

    assert len(results) == 1
    assert not results[0]["ok"]
    assert "sandboxed" in results[0]["error"]
    assert calls == []


def test_local_web_sandbox_turn_binds_server_created_room_scope(monkeypatch):
    from types import SimpleNamespace

    from uagent.runtime.execution_broker import current_scope

    monkeypatch.setattr(
        web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", True, raising=False)
    room = SimpleNamespace(room_id="server-room-1")
    turn = SimpleNamespace(
        entry_point="web",
        room_id="server-room-1",
        principal_id="local-user",
        project_id="local-project",
    )
    identity = SimpleNamespace(
        authenticated=True,
        authn_kind="local",
        principal_id="local-user",
    )

    from uagent.web_impl.agent_worker import _web_turn_execution_context

    context = _web_turn_execution_context(room, turn, identity, "C:/project")
    with context:
        scope = current_scope()
        assert scope is not None
        assert scope.deployment_id == "web"
        assert scope.principal_id == "local-user"
        assert scope.project_id == "local-project"
        assert scope.scope_kind == "web-room"
        assert scope.scope_id.startswith("server-room-1-")
    assert current_scope() is None


def test_local_web_sandbox_rejects_missing_trusted_room_context(monkeypatch):
    from types import SimpleNamespace

    from uagent.runtime.identity_context import IdentityResolutionError

    monkeypatch.setattr(
        web_manager, "execution_profile", "local_trusted", raising=False
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", True, raising=False)

    with pytest.raises(IdentityResolutionError, match="trusted local Room"):
        from uagent.web_impl.agent_worker import _web_turn_execution_context

        _web_turn_execution_context(SimpleNamespace(room_id="room"), None, None, None)


def test_web_sandbox_mode_resolution_uses_loaded_environment_and_cli_precedence():
    assert init._resolve_web_sandbox_mode(None, "mxc") == "mxc"
    assert init._resolve_web_sandbox_mode("off", "mxc") == "off"

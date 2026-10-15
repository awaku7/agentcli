from __future__ import annotations

import json
from pathlib import Path

import pytest

from uagent import hooks_engine, tools
from uagent.runtime import mxc_backend, sandbox_worker
from uagent.runtime.execution_broker import (
    IsolationLevel,
    SandboxCapabilities,
    SandboxCapability,
    SecurityProfile,
    TrustedSandboxScope,
    execution_profile,
    required_sandbox_capabilities,
)


def test_node_helper_pins_the_verified_mxc_sdk_version():
    helper = (
        Path(__file__).parents[1] / "src" / "uagent" / "runtime" / "mxc_node_helper"
    )
    manifest = json.loads((helper / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((helper / "package-lock.json").read_text(encoding="utf-8"))
    assert manifest["dependencies"]["@microsoft/mxc-sdk"] == "1.0.0"
    assert lock["packages"]["node_modules/@microsoft/mxc-sdk"]["version"] == "1.0.0"


@pytest.fixture
def local_scope() -> TrustedSandboxScope:
    return TrustedSandboxScope(
        deployment_id="cli",
        principal_id="test-user",
        project_id="test-project",
        scope_kind="cli-session",
        scope_id="test-session",
    )


def all_local_capabilities() -> SandboxCapabilities:
    return SandboxCapabilities(
        isolation_level=IsolationLevel.CONTAINER,
        available=frozenset(SandboxCapability),
    )


def test_mxc_backend_rejects_non_windows_without_trying_to_install(monkeypatch):
    monkeypatch.setattr(mxc_backend.os, "name", "posix")
    monkeypatch.setattr(
        mxc_backend,
        "_find_node",
        lambda: (_ for _ in ()).throw(AssertionError("Node lookup must not run")),
    )
    with pytest.raises(RuntimeError, match="Windows x64"):
        mxc_backend.prepare_mxc_runtime(allow_install=True)


def test_remote_profile_still_requires_vm_even_with_processcontainer_caps():
    caps = all_local_capabilities()
    minimum, required = required_sandbox_capabilities(SecurityProfile.REMOTE)
    assert not caps.satisfies(minimum_isolation=minimum, required=required)
    assert minimum is IsolationLevel.VM


def test_sandbox_tool_catalog_is_static_and_does_not_load_host_plugins(
    monkeypatch, local_scope
):
    monkeypatch.setattr(
        tools,
        "_ensure_loaded",
        lambda: (_ for _ in ()).throw(AssertionError("Host plugins must not load")),
    )
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=local_scope
    ):
        names = {spec["function"]["name"] for spec in tools.get_tool_specs()}
    assert names == set(mxc_backend.TOOL_NAMES)


def test_sandbox_route_fails_closed_when_backend_is_not_initialized(
    monkeypatch, local_scope
):
    called = []
    monkeypatch.setitem(tools._RUNNERS, "file_exists", lambda args: called.append(args))
    monkeypatch.setattr(
        tools,
        "_ensure_loaded",
        lambda: (_ for _ in ()).throw(AssertionError("Host runner was reached")),
    )
    monkeypatch.setattr(mxc_backend, "install_session_manager", lambda _: None)
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=local_scope
    ):
        result = tools.run_tool("file_exists", {"path": "inside.txt"})
    assert "no compliant sandbox backend" in result
    assert called == []


def test_sandbox_calls_adapter_before_host_runner(monkeypatch, local_scope):
    class FakeManager:
        capabilities = all_local_capabilities()

        def run_tool(self, scope, name, args):
            assert scope == local_scope
            assert name == "file_exists"
            assert args == {"path": "inside.txt"}
            return '{"exists":true,"is_file":true,"is_dir":false}'

    fake = FakeManager()
    monkeypatch.setattr(mxc_backend, "current_session_manager", lambda: fake)
    monkeypatch.setattr(
        tools,
        "_ensure_loaded",
        lambda: (_ for _ in ()).throw(AssertionError("Host plugins must not load")),
    )
    monkeypatch.setattr(tools, "_emit_tool_trace", lambda *args: None)
    monkeypatch.setattr(tools, "_CONFIRMATION_CALLBACK", lambda *args: True)
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=local_scope
    ):
        result = tools.run_tool("file_exists", {"path": "inside.txt"})
    assert result == '{"exists":true,"is_file":true,"is_dir":false}'


def test_sandbox_parallel_safety_does_not_load_host_plugins(monkeypatch, local_scope):
    monkeypatch.setattr(
        tools,
        "_ensure_loaded",
        lambda: (_ for _ in ()).throw(AssertionError("Host plugins must not load")),
    )
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=local_scope
    ):
        assert tools.is_parallel_safe("file_exists", {"path": "a.txt"})
        assert tools.is_parallel_safe("read_file", {"path": "a.txt"})
        assert not tools.is_parallel_safe("create_file", {"filename": "a.txt"})
        assert not tools.is_parallel_safe("python_exec", {"code": "print(1)"})


def test_sandboxed_local_hooks_cannot_run_host_commands(monkeypatch, local_scope):
    monkeypatch.setattr(
        hooks_engine,
        "_execute_command_hook",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Host hook command must not run")
        ),
    )
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=local_scope
    ):
        result = hooks_engine.execute_hook(
            {"type": "command", "command": "echo unsafe"}, event_name="SessionStart"
        )
    assert result["ok"] is False
    assert "denied" in result["error"]


def test_unallowlisted_local_tool_is_denied_before_plugin_load(
    monkeypatch, local_scope
):
    monkeypatch.setattr(mxc_backend, "current_session_manager", lambda: None)
    monkeypatch.setattr(
        tools,
        "_ensure_loaded",
        lambda: (_ for _ in ()).throw(AssertionError("Host plugins must not load")),
    )
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=local_scope
    ):
        result = tools.run_tool("cmd_exec_json", {"command": "echo unsafe"})
    assert "not available in the local sandbox" in result


def test_worker_file_tools_are_workspace_relative_and_reject_traversal(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(sandbox_worker, "ROOT", tmp_path.resolve())
    assert (
        sandbox_worker._dispatch(
            {
                "name": "create_file",
                "args": {"filename": "nested/hello.txt", "content": "hello"},
            }
        )
        == "Created nested/hello.txt"
    )
    assert (
        sandbox_worker._dispatch(
            {"name": "read_file", "args": {"path": "nested/hello.txt"}}
        )
        == "hello"
    )
    result = json.loads(
        sandbox_worker._dispatch(
            {"name": "file_exists", "args": {"path": "nested/hello.txt"}}
        )
    )
    assert result == {"exists": True, "is_file": True, "is_dir": False}
    with pytest.raises(ValueError, match="traversal"):
        sandbox_worker._dispatch(
            {"name": "read_file", "args": {"path": "../outside.txt"}}
        )


def test_worker_rejects_absolute_paths_and_unregistered_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_worker, "ROOT", tmp_path.resolve())
    with pytest.raises(ValueError, match="absolute paths"):
        sandbox_worker._dispatch(
            {"name": "read_file", "args": {"path": str(tmp_path / "file.txt")}}
        )
    with pytest.raises(ValueError, match="allowlist"):
        sandbox_worker._dispatch(
            {"name": "http_request", "args": {"url": "https://example.com"}}
        )


def test_scope_key_does_not_expose_session_identifiers(local_scope):
    hashed = mxc_backend._scope_key(local_scope)
    assert len(hashed) == 64
    assert "test-user" not in hashed
    assert "test-session" not in hashed


def test_manager_caps_active_session_workers(monkeypatch, tmp_path):
    class FakeProc:
        def poll(self):
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._closed = False
            self._proc = FakeProc()

        def run(self, name, args):
            return "isolated"

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    scopes = [
        TrustedSandboxScope(
            deployment_id="cli",
            principal_id="user",
            project_id="project",
            scope_kind="cli-session",
            scope_id=f"session-{i}",
        )
        for i in range(mxc_backend.MAX_ACTIVE_SESSIONS + 1)
    ]
    for scope in scopes[: mxc_backend.MAX_ACTIVE_SESSIONS]:
        assert manager.run_tool(scope, "file_exists", {"path": "x"}) == "isolated"
    assert "active session limit" in manager.run_tool(
        scopes[-1], "file_exists", {"path": "x"}
    )
    assert len(manager._sessions) == mxc_backend.MAX_ACTIVE_SESSIONS
    manager.close_all()


def test_manager_refuses_a2a_scope_without_spawning(tmp_path):
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    a2a_scope = TrustedSandboxScope(
        deployment_id="a2a",
        principal_id="service",
        project_id="project",
        scope_kind="a2a-task",
        scope_id="task",
    )
    assert "trusted local CLI/GUI/Web Room scope" in manager.run_tool(
        a2a_scope, "file_exists", {"path": "x"}
    )
    assert manager._sessions == {}


def test_read_file_result_is_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_worker, "ROOT", tmp_path.resolve())
    (tmp_path / "large.txt").write_text("x" * (sandbox_worker.MAX_TEXT_BYTES + 5))
    result = sandbox_worker._dispatch(
        {"name": "read_file", "args": {"path": "large.txt", "max_bytes": 100}}
    )
    assert result == "x" * 100


def test_local_web_room_scope_routes_tools_only_to_the_sandbox_manager(
    monkeypatch,
):
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="local-project",
        scope_kind="web-room",
        scope_id="room-1",
    )
    observed = []

    class Manager:
        capabilities = all_local_capabilities()

        def run_tool(self, received_scope, name, args):
            observed.append((received_scope, name, args))
            return "sandbox-result"

    manager = Manager()
    monkeypatch.setattr(mxc_backend, "current_session_manager", lambda: manager)
    monkeypatch.setitem(
        tools._RUNNERS,
        "file_exists",
        lambda _args: (_ for _ in ()).throw(
            AssertionError("sandbox route reached the Host runner")
        ),
    )

    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=scope
    ):
        result = tools.run_tool("file_exists", {"path": "inside.txt"})

    assert result == "sandbox-result"
    assert observed == [(scope, "file_exists", {"path": "inside.txt"})]


def test_startup_scope_without_session_id_uses_process_unique_fallback(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 54321)

    scope = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id=""
    )

    assert scope.scope_id.startswith("cli-54321-")
    assert len(scope.scope_id.rsplit("-", 1)[-1]) == 32

    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 54322)
    other_process_scope = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id=""
    )
    assert other_process_scope.scope_id != scope.scope_id


def test_mxc_session_manager_accepts_only_matching_local_web_room_scope(
    monkeypatch, tmp_path
):
    observed = []

    class FakeProcess:
        @staticmethod
        def poll():
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            observed.append((scope, node, runtime))
            self._closed = False
            self._proc = FakeProcess()

        @staticmethod
        def run(name, args):
            return f"{name}:{args['path']}"

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    scope = TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="local-project",
        scope_kind="web-room",
        scope_id="room-7",
    )

    assert manager.run_tool(scope, "file_exists", {"path": "inside.txt"}) == (
        "file_exists:inside.txt"
    )
    assert observed[0][0] == scope

    wrong_binding = TrustedSandboxScope(
        deployment_id="cli",
        principal_id="local-user",
        project_id="local-project",
        scope_kind="web-room",
        scope_id="room-8",
    )
    assert "trusted local" in manager.run_tool(
        wrong_binding, "file_exists", {"path": "inside.txt"}
    )

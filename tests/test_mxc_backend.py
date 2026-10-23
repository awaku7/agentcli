from __future__ import annotations

import io
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

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


def test_mxc_host_paths_ignore_project_dotenv_values(monkeypatch, tmp_path):
    from uagent.runtime import runtime_init

    local_app_data = tmp_path / "local-app-data"
    project = tmp_path / "project"
    local_app_data.mkdir()
    project.mkdir()
    project_node = project / "node.exe"
    project_runtime = project / "mxc-runtime"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("UAGENT_MXC_NODE", str(project_node))
    monkeypatch.setenv("UAGENT_MXC_RUNTIME_DIR", str(project_runtime))
    monkeypatch.setattr(runtime_init, "get_startup_uagent_env_snapshot", lambda: {})

    assert project_node not in mxc_backend._node_candidates()
    assert mxc_backend._runtime_dir() == local_app_data / "uagent" / "mxc_runtime"


def test_mxc_host_paths_accept_only_pre_dotenv_overrides(monkeypatch, tmp_path):
    from uagent.runtime import runtime_init

    local_app_data = tmp_path / "local-app-data"
    trusted_node = local_app_data / "uagent" / "toolchains" / "node.exe"
    trusted_runtime = local_app_data / "uagent" / "mxc_runtime_test"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("UAGENT_MXC_NODE", str(tmp_path / "project-node.exe"))
    monkeypatch.setenv("UAGENT_MXC_RUNTIME_DIR", str(tmp_path / "project-runtime"))
    monkeypatch.setattr(
        runtime_init,
        "get_startup_uagent_env_snapshot",
        lambda: {
            "UAGENT_MXC_NODE": str(trusted_node),
            "UAGENT_MXC_RUNTIME_DIR": str(trusted_runtime),
        },
    )

    assert trusted_node in mxc_backend._node_candidates()
    assert mxc_backend._runtime_dir() == trusted_runtime


@pytest.mark.skipif(os.name != "nt", reason="MXC runtime setup is Windows-only")
def test_prepare_mxc_runtime_rejects_project_as_helper_root(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr(mxc_backend, "_find_node", lambda: project / "node.exe")
    monkeypatch.setattr(mxc_backend, "_node_version", lambda _node: (24, 22, 0))
    monkeypatch.setattr(mxc_backend.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(mxc_backend, "_runtime_dir", lambda: project)

    with pytest.raises(RuntimeError, match="selected work directory"):
        mxc_backend.prepare_mxc_runtime(allow_install=False)

    assert list(project.iterdir()) == []


def test_node_version_uses_only_the_node_and_system_directories(monkeypatch, tmp_path):
    node = tmp_path / "toolchain" / "node.exe"
    system_root = tmp_path / "windows"
    project_path = tmp_path / "project-bin"
    captured = {}

    def fake_run(_args, **kwargs):
        captured.update(kwargs["env"])
        return SimpleNamespace(stdout="v24.22.0")

    monkeypatch.setenv("SystemRoot", str(system_root))
    monkeypatch.setenv("PATH", str(project_path))
    monkeypatch.setattr(mxc_backend.subprocess, "run", fake_run)

    assert mxc_backend._node_version(node) == (24, 22, 0)
    assert captured["PATH"] == os.pathsep.join(
        (str(node.parent), str(system_root / "System32"))
    )
    assert str(project_path) not in captured["PATH"]


def test_mxc_host_overrides_must_be_absolute(monkeypatch):
    from uagent.runtime import runtime_init

    monkeypatch.setattr(
        runtime_init,
        "get_startup_uagent_env_snapshot",
        lambda: {
            "UAGENT_MXC_NODE": "node.exe",
            "UAGENT_MXC_RUNTIME_DIR": "mxc-runtime",
        },
    )

    with pytest.raises(RuntimeError, match="UAGENT_MXC_NODE must be an absolute"):
        mxc_backend._node_candidates()
    with pytest.raises(
        RuntimeError, match="UAGENT_MXC_RUNTIME_DIR must be an absolute"
    ):
        mxc_backend._runtime_dir()


def test_mxc_requests_explicitly_forbid_host_dacl_mutation():
    helper = (
        Path(__file__).parents[1] / "src" / "uagent" / "runtime" / "mxc_node_helper"
    )
    source = (helper / "mxc_adapter.mjs").read_text(encoding="utf-8")
    assert source.count("fallback: { allowDaclMutation: false }") == 2


def test_python_workspace_monitor_stays_active_until_mxc_wait():
    helper = (
        Path(__file__).parents[1] / "src" / "uagent" / "runtime" / "mxc_node_helper"
    )
    source = (helper / "mxc_adapter.mjs").read_text(encoding="utf-8")
    outcome = source.index("const outcome = await Promise.race(")
    stop = source.index("const stopThroughMxc = async () => {", outcome)
    kill = source.index("try { processHandle.kill(); } catch {", stop)
    wait = source.index("acceptRootExit(await waitForRoot", kill)
    monitor_stop = source.index("clearInterval(workspaceMonitor);", wait)
    assert outcome < stop < kill < wait < monitor_stop
    assert source.index("await workspaceMonitorPromise;", monitor_stop) > monitor_stop
    assert source.index("clearTimeout(executionTimer);", monitor_stop) > monitor_stop


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


def test_processcontainer_probe_never_claims_remote_acceptance(monkeypatch, tmp_path):
    node = tmp_path / "node.exe"
    runtime = tmp_path / "mxc-runtime"
    monkeypatch.setattr(
        mxc_backend,
        "prepare_mxc_runtime",
        lambda *, allow_install=False: (node, runtime),
    )
    monkeypatch.setattr(
        mxc_backend,
        "_run_probe",
        lambda _node, _runtime: {"backend": "processcontainer"},
    )

    capabilities, report, probed_node, probed_runtime = mxc_backend.probe_mxc_backend()

    assert report["backend"] == "processcontainer"
    assert probed_node == node
    assert probed_runtime == runtime
    assert capabilities.isolation_level is IsolationLevel.CONTAINER
    assert capabilities.remote_acceptance_passed is False


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


def test_worker_read_file_applies_byte_limit_after_start_line(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_worker, "ROOT", tmp_path.resolve())
    target = tmp_path / "large.txt"
    target.write_bytes(b"line\n" * 250_000 + b"later section\n")

    result = sandbox_worker._dispatch(
        {
            "name": "read_file",
            "args": {
                "path": "large.txt",
                "start_line": 250_001,
                "max_bytes": 100,
            },
        }
    )

    assert result == "later section\n"


def test_workspace_quota_scan_tolerates_vanished_children():
    helper = (
        Path(__file__).parents[1] / "src" / "uagent" / "runtime" / "mxc_node_helper"
    )
    source = (helper / "mxc_adapter.mjs").read_text(encoding="utf-8")
    start = source.index("function workspaceUsage(root)")
    end = source.index("async function executePythonInContainer", start)
    scanner = source[start:end]

    assert 'entry !== rootPath && error?.code === "ENOENT"' in scanner
    assert scanner.count("if (vanishedChild(entry, error))") == 4


def test_alternate_stream_scan_tolerates_vanished_files():
    helper = (
        Path(__file__).parents[1] / "src" / "uagent" / "runtime" / "mxc_node_helper"
    )
    source = (helper / "mxc_adapter.mjs").read_text(encoding="utf-8")
    start = source.index("const ALTERNATE_STREAM_SCAN_SCRIPT = [")
    end = source.index("async function alternateStreamUsage(root)", start)
    scanner = source[start:end]

    assert scanner.count("$winError -eq 2 -or $winError -eq 3") == 2
    assert "if (-not $isRoot" in scanner
    assert "Test-VanishedWorkspacePathError" in scanner
    assert "ErrorCategory]::ObjectNotFound" in scanner
    assert "async function alternateStreamUsage(root)" in source
    assert "const { stdout: output } = await execFileAsync(" in source
    assert "$pending = [System.Collections.Generic.Stack[string]]::new()" in scanner
    assert (
        "Get-ChildItem -LiteralPath $directoryPath -Force -ErrorAction Stop" in scanner
    )
    assert "Get-ChildItem -LiteralPath $root -Force -Recurse" not in scanner
    assert "$itemTotal += [long]$streamData.StreamSize" in scanner
    assert "$total += $itemTotal" in scanner


def test_non_python_tool_writes_are_checked_against_workspace_quota():
    helper = (
        Path(__file__).parents[1] / "src" / "uagent" / "runtime" / "mxc_node_helper"
    )
    source = (helper / "mxc_adapter.mjs").read_text(encoding="utf-8")
    start = source.index("const reply = nextReply(HARD_EXECUTION_TIMEOUT_MS + 5_000);")
    end = source.index("if (result?.terminate === true)", start)
    handler = source[start:end]

    assert "usage = await workspaceUsage(workspace)" in handler
    assert handler.index("workspaceUsage(workspace)") < handler.index(
        "if (usage.exceeded)"
    )
    assert 'terminate: true, error: "session workspace limit exceeded;' in handler
    assert handler.index("await stopWorker()") < handler.index("writeHost(result)")


def test_python_completion_uses_mxc_wait_and_fails_closed():
    helper = (
        Path(__file__).parents[1] / "src" / "uagent" / "runtime" / "mxc_node_helper"
    )
    source = (helper / "mxc_adapter.mjs").read_text(encoding="utf-8")

    assert "const waitPromise = processHandle.wait();" in source
    assert "processHandle.kill();" in source
    assert "executionIncomplete = markerExitCode === null;" in source
    assert "process_tree_unverified: processTreeUnverified" in source
    assert "execution_incomplete: executionIncomplete" in source
    assert "Python execution exited before its completion marker" in source
    assert source.index("if (result.workspace_limit_exceeded)") < source.index(
        "if (result.execution_incomplete)"
    )
    assert "terminateMxcProcessTree" not in source
    assert "taskkill.exe" not in source


def test_worker_read_file_never_exceeds_serialized_result_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_worker, "ROOT", tmp_path.resolve())
    target = tmp_path / "controls.txt"
    target.write_bytes(b"\x00" * (sandbox_worker.MAX_READ_BYTES * 2))

    result = sandbox_worker._read_file({"path": "controls.txt", "max_bytes": 1_000_000})
    assert len(result) == sandbox_worker.MAX_READ_BYTES

    captured = io.StringIO()
    monkeypatch.setattr(sandbox_worker.sys, "stdout", captured)
    sandbox_worker._emit({"ok": True, "result": result})
    output = captured.getvalue()
    assert "tool result exceeds the bounded response limit" not in output
    assert len(output.encode("utf-8")) <= sandbox_worker.MAX_RESULT_BYTES + 1

    spec = next(
        item
        for item in mxc_backend.sandbox_tool_specs()
        if item["function"]["name"] == "read_file"
    )
    assert spec["function"]["parameters"]["properties"]["max_bytes"]["maximum"] == (
        sandbox_worker.MAX_READ_BYTES
    )


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("read_file", {"path": "carrier:payload"}),
        ("create_file", {"filename": "carrier:payload", "content": "x"}),
    ],
)
def test_worker_rejects_alternate_data_stream_paths(monkeypatch, tmp_path, name, args):
    monkeypatch.setattr(sandbox_worker, "ROOT", tmp_path.resolve())

    with pytest.raises(ValueError, match="alternate data stream"):
        sandbox_worker._dispatch({"name": name, "args": args})


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


def test_manager_closes_obsolete_gui_session_after_session_transition():
    import threading

    old_scope = TrustedSandboxScope(
        deployment_id="gui",
        principal_id="local-user",
        project_id="project",
        scope_kind="gui-session",
        scope_id="old-session",
    )
    new_scope = TrustedSandboxScope(
        deployment_id="gui",
        principal_id="local-user",
        project_id="project",
        scope_kind="gui-session",
        scope_id="new-session",
    )

    class FakeSession:
        _scope = old_scope
        closed = False

        def close(self):
            self.closed = True

    session = FakeSession()
    manager = object.__new__(mxc_backend.MxcSessionManager)
    manager._sessions = {"old-key": session}
    manager._active_local_scopes = {
        (
            old_scope.deployment_id,
            old_scope.principal_id,
            old_scope.scope_kind,
        ): old_scope
    }
    manager._lock = threading.RLock()

    manager.activate_scope(new_scope)

    assert session.closed
    assert manager._sessions == {}
    assert manager.run_tool(old_scope, "file_exists", {"path": "x"}) == (
        "[sandbox error] stale local execution scope rejected"
    )
    assert manager._sessions == {}


def test_manager_rejects_stale_gui_scope_after_workdir_change(monkeypatch, tmp_path):
    created_projects = []

    class FakeProc:
        def poll(self):
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._scope = scope
            self._closed = False
            self._proc = FakeProc()
            created_projects.append(scope.project_id)

        def run(self, name, args):
            return self._scope.project_id

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    old_scope = TrustedSandboxScope(
        deployment_id="gui",
        principal_id="local-user",
        project_id="old-workdir",
        scope_kind="gui-session",
        scope_id="same-session",
    )
    new_scope = TrustedSandboxScope(
        deployment_id="gui",
        principal_id="local-user",
        project_id="new-workdir",
        scope_kind="gui-session",
        scope_id="same-session",
    )

    manager.activate_scope(old_scope)
    assert manager.run_tool(old_scope, "file_exists", {"path": "x"}) == "old-workdir"
    manager.activate_scope(new_scope)

    assert manager.run_tool(old_scope, "file_exists", {"path": "x"}) == (
        "[sandbox error] stale local execution scope rejected"
    )
    assert manager.run_tool(new_scope, "file_exists", {"path": "x"}) == "new-workdir"
    assert created_projects == ["old-workdir", "new-workdir"]
    manager.close_all()


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


def test_local_web_room_scope_is_unique_per_process(monkeypatch):
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 54321)
    scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="project",
        room_id="room-1",
        room_generation="generation-1",
    )

    assert scope.deployment_id == "web"
    assert scope.scope_kind == "web-room"
    assert scope.scope_id.startswith("room-1-54321-")
    recreated_room_scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="project",
        room_id="room-1",
        room_generation="generation-2",
    )
    assert recreated_room_scope.scope_id != scope.scope_id

    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 54322)
    other_process_scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="project",
        room_id="room-1",
        room_generation="generation-1",
    )
    assert other_process_scope.scope_id != scope.scope_id


def test_closing_evicted_room_scope_does_not_close_recreated_room_scope(
    monkeypatch, tmp_path
):
    class FakeProcess:
        @staticmethod
        def poll():
            return None

    sessions = []

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._scope = scope
            self._closed = False
            self._proc = FakeProcess()
            sessions.append(self)

        def run(self, name, args):
            return f"{name}:{self._scope.scope_id}"

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    old_scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="project",
        room_id="room-1",
        room_generation="old-room-instance",
    )
    recreated_scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="project",
        room_id="room-1",
        room_generation="new-room-instance",
    )

    manager.activate_scope(old_scope)
    manager.run_tool(old_scope, "file_exists", {"path": "old.txt"})
    manager.activate_scope(recreated_scope)
    manager.run_tool(recreated_scope, "file_exists", {"path": "new.txt"})
    manager.close_scope(old_scope)

    assert sessions[0]._closed
    assert not sessions[1]._closed
    assert manager.run_tool(recreated_scope, "file_exists", {"path": "newer.txt"})
    manager.close_all()


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
    scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="local-project",
        room_id="room-7",
        room_generation="generation-1",
    )
    manager.activate_scope(scope)

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


def test_manager_fences_revoked_web_room_scopes(monkeypatch, tmp_path):
    created_scopes = []

    class FakeProcess:
        @staticmethod
        def poll():
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._scope = scope
            self._closed = False
            self._proc = FakeProcess()
            created_scopes.append(scope)

        def run(self, _name, _args):
            return self._scope.scope_id

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="project",
        room_id="room-a",
        room_generation="generation-a",
    )

    assert "revoked or unbound" in manager.run_tool(scope, "file_exists", {"path": "x"})
    manager.activate_scope(scope)
    assert manager.run_tool(scope, "file_exists", {"path": "x"}) == scope.scope_id
    cleanup = manager.revoke_scope(scope)
    assert cleanup is not None
    cleanup()

    assert "revoked or unbound" in manager.run_tool(scope, "file_exists", {"path": "x"})
    fresh_scope = mxc_backend.local_web_room_scope(
        principal_id="local-user",
        project_id="project",
        room_id="room-a",
        room_generation="generation-b",
    )
    manager.activate_scope(fresh_scope)
    assert (
        manager.run_tool(fresh_scope, "file_exists", {"path": "x"})
        == fresh_scope.scope_id
    )
    assert created_scopes == [scope, fresh_scope]
    manager.close_all()


def test_revocation_blocks_web_tool_queued_on_session_lock(monkeypatch, tmp_path):
    import threading

    class FakeProcess:
        @staticmethod
        def poll():
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._scope = scope
            self._closed = False
            self._proc = FakeProcess()
            self._lock = threading.RLock()
            self._revoked = threading.Event()
            self.run_attempted = threading.Event()
            self.executed = []

        def run(self, name, _args):
            self.run_attempted.set()
            with self._lock:
                if self._revoked.is_set():
                    raise PermissionError("sandbox scope has been revoked")
                self.executed.append(name)
                return "executed"

        def revoke(self):
            self._revoked.set()

        def close(self):
            with self._lock:
                self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    scope = mxc_backend.local_web_room_scope(
        principal_id="alice",
        project_id="project",
        room_id="room-a",
        room_generation="generation-a",
    )
    manager.activate_scope(scope)
    assert manager.run_tool(scope, "file_exists", {"path": "first"}) == "executed"
    session = manager._sessions[mxc_backend._scope_key(scope)]

    outcome = []
    with session._lock:
        worker = threading.Thread(
            target=lambda: outcome.append(
                manager.run_tool(scope, "read_file", {"path": "queued"})
            )
        )
        worker.start()
        assert session.run_attempted.wait(1)
        cleanup = manager.revoke_scope(scope)
        assert cleanup is not None
        assert session._revoked.is_set()

    worker.join(2)
    assert not worker.is_alive()
    assert len(outcome) == 1
    assert "revoked" in outcome[0]
    assert session.executed == ["file_exists"]
    cleanup()
    manager.close_all()


def test_web_room_release_revokes_scope_before_fresh_binding(monkeypatch, tmp_path):
    from uagent.web_impl.rooms import WebManager

    class FakeProcess:
        @staticmethod
        def poll():
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._scope = scope
            self._closed = False
            self._proc = FakeProcess()

        def run(self, _name, _args):
            return self._scope.scope_id

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    sessions = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    rooms = WebManager()
    rooms.sandbox_session_manager = sessions
    room = rooms.get_room("room-a")
    scope = mxc_backend.local_web_room_scope(
        principal_id="alice",
        project_id="project-a",
        room_id=room.room_id,
        room_generation=room.sandbox_scope_generation(),
    )
    rooms.bind_sandbox_scope(room, scope)
    assert sessions.run_tool(scope, "file_exists", {"path": "x"}) == scope.scope_id

    assert rooms.release_room_sandbox_scope(room, expected_scope=scope)
    assert "revoked or unbound" in sessions.run_tool(
        scope, "file_exists", {"path": "x"}
    )
    fresh_scope = mxc_backend.local_web_room_scope(
        principal_id="alice",
        project_id="project-a",
        room_id=room.room_id,
        room_generation=room.sandbox_scope_generation(),
    )
    rooms.bind_sandbox_scope(room, fresh_scope)
    assert (
        sessions.run_tool(fresh_scope, "file_exists", {"path": "x"})
        == fresh_scope.scope_id
    )
    sessions.close_all()


def test_web_room_release_fences_scope_before_detaching_lease(monkeypatch, tmp_path):
    from uagent.web_impl.rooms import WebManager

    created_scopes = []

    class FakeProcess:
        @staticmethod
        def poll():
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._scope = scope
            self._closed = False
            self._proc = FakeProcess()
            created_scopes.append(scope)

        def run(self, _name, _args):
            return self._scope.scope_id

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    session_manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    web_manager = WebManager()
    web_manager.sandbox_session_manager = session_manager
    room = web_manager.get_room("room-a")
    scope = mxc_backend.local_web_room_scope(
        principal_id="alice",
        project_id="project-a",
        room_id=room.room_id,
        room_generation=room.sandbox_scope_generation(),
    )
    web_manager.bind_sandbox_scope(room, scope)
    assert session_manager.run_tool(scope, "file_exists", {"path": "x"}) == (
        scope.scope_id
    )

    assert web_manager.release_room_sandbox_scope(room, expected_scope=scope)
    assert room.current_sandbox_scope() is None
    assert room.sandbox_scope_generation() != scope.binding_generation
    assert "revoked or unbound" in session_manager.run_tool(
        scope, "file_exists", {"path": "x"}
    )

    fresh_scope = mxc_backend.local_web_room_scope(
        principal_id="alice",
        project_id="project-a",
        room_id=room.room_id,
        room_generation=room.sandbox_scope_generation(),
    )
    web_manager.bind_sandbox_scope(room, fresh_scope)
    assert session_manager.run_tool(fresh_scope, "file_exists", {"path": "x"}) == (
        fresh_scope.scope_id
    )
    assert created_scopes == [scope, fresh_scope]
    session_manager.close_all()


def test_manager_prunes_inactive_sessions_before_enforcing_limit(monkeypatch, tmp_path):
    class FakeProcess:
        def __init__(self, exit_code=None):
            self.exit_code = exit_code

        def poll(self):
            return self.exit_code

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._closed = False
            self._proc = FakeProcess()
            self.close_called = False

        def run(self, name, args):
            return "session-result"

        def close(self):
            self.close_called = True
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    inactive = []
    for index in range(mxc_backend.MAX_ACTIVE_SESSIONS):
        stale_scope = TrustedSandboxScope(
            deployment_id="cli",
            principal_id="local-user",
            project_id="project",
            scope_kind="cli-session",
            scope_id=f"stale-{index}",
        )
        stale_session = FakeSession(
            scope=stale_scope, node=manager.node, runtime=manager.runtime
        )
        if index % 2:
            stale_session._closed = True
        else:
            stale_session._proc.exit_code = 1
        manager._sessions[mxc_backend._scope_key(stale_scope)] = stale_session
        inactive.append(stale_session)

    new_scope = TrustedSandboxScope(
        deployment_id="cli",
        principal_id="local-user",
        project_id="project",
        scope_kind="cli-session",
        scope_id="new-scope",
    )

    assert manager.run_tool(new_scope, "file_exists", {"path": "x"}) == (
        "session-result"
    )
    assert all(session.close_called for session in inactive)
    assert set(manager._sessions) == {mxc_backend._scope_key(new_scope)}


def test_cli_session_transition_releases_previous_worker(monkeypatch, tmp_path):
    class FakeProcess:
        def poll(self):
            return None

    class FakeSession:
        def __init__(self, *, scope, node, runtime):
            self._scope = scope
            self._closed = False
            self._proc = FakeProcess()

        def run(self, name, args):
            return f"{name}:{args['path']}"

        def close(self):
            self._closed = True

    monkeypatch.setattr(mxc_backend, "_MxcSession", FakeSession)
    manager = mxc_backend.MxcSessionManager(
        node=tmp_path / "node.exe",
        runtime=tmp_path,
        capabilities=all_local_capabilities(),
    )
    first = TrustedSandboxScope(
        deployment_id="cli",
        principal_id="local-user",
        project_id="project",
        scope_kind="cli-session",
        scope_id="session-one",
    )
    second = TrustedSandboxScope(
        deployment_id="cli",
        principal_id="local-user",
        project_id="project",
        scope_kind="cli-session",
        scope_id="session-two",
    )

    assert manager.run_tool(first, "read_file", {"path": "one.txt"}) == (
        "read_file:one.txt"
    )
    old_session = manager._sessions[mxc_backend._scope_key(first)]
    assert manager.run_tool(second, "read_file", {"path": "two.txt"}) == (
        "read_file:two.txt"
    )

    assert old_session._closed is True
    assert set(manager._sessions) == {mxc_backend._scope_key(second)}


def test_workspace_scavenger_removes_only_unleased_workspaces(tmp_path):
    key = "a" * 64
    root = tmp_path / "sandboxes"
    workspace = root / key
    workspace.mkdir(parents=True)
    readonly_file = workspace / "data.txt"
    readonly_file.write_text("test", encoding="utf-8")
    readonly_file.chmod(stat.S_IREAD)

    lease = mxc_backend._acquire_workspace_lease(root, key)
    assert lease is not None
    mxc_backend._scavenge_orphaned_workspaces(root)
    assert workspace.is_dir()

    mxc_backend._release_workspace_lease(lease)
    mxc_backend._scavenge_orphaned_workspaces(root)
    assert not workspace.exists()
    assert not mxc_backend._workspace_lease_path(root, key).exists()


def test_workspace_scavenger_skips_one_unremovable_directory(monkeypatch, tmp_path):
    key = "b" * 64
    root = tmp_path / "sandboxes"
    workspace = root / key
    workspace.mkdir(parents=True)
    lease = mxc_backend._acquire_workspace_lease(root, key)
    assert lease is not None
    mxc_backend._release_workspace_lease(lease)

    def fail_remove(_workspace):
        raise PermissionError("simulated stale workspace failure")

    with monkeypatch.context() as patch:
        patch.setattr(mxc_backend, "_remove_workspace_tree", fail_remove)
        mxc_backend._scavenge_orphaned_workspaces(root)

    assert workspace.is_dir()
    assert mxc_backend._workspace_lease_path(root, key).exists()
    mxc_backend._scavenge_orphaned_workspaces(root)
    assert not workspace.exists()


def test_python_prefix_cannot_contain_the_selected_work_directory(
    monkeypatch, tmp_path
):
    prefix = tmp_path / "venv"
    project = prefix / "project"
    project.mkdir(parents=True)
    monkeypatch.chdir(project)

    with pytest.raises(RuntimeError, match="selected work directory"):
        mxc_backend._validate_sandbox_read_root(prefix)
    with pytest.raises(RuntimeError, match="selected work directory"):
        mxc_backend._validate_sandbox_read_root(
            prefix, require_existing_directory=False
        )
    with pytest.raises(RuntimeError, match="filesystem roots"):
        mxc_backend._validate_sandbox_read_root(Path(tmp_path.anchor))

    profile = tmp_path / "profile"
    profile.mkdir()
    outside_workdir = tmp_path / "outside-workdir"
    outside_workdir.mkdir()
    monkeypatch.setenv("USERPROFILE", str(profile))
    monkeypatch.chdir(outside_workdir)
    with pytest.raises(RuntimeError, match="per-user data"):
        mxc_backend._validate_sandbox_read_root(profile)

    external_prefix = tmp_path / "external-venv"
    external_prefix.mkdir()
    assert (
        mxc_backend._validate_sandbox_read_root(external_prefix)
        == external_prefix.resolve()
    )


def test_startup_scope_persisted_session_is_process_instance_specific(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 54321)
    first = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="saved-session"
    )
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 54322)
    second = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="saved-session"
    )

    assert first.scope_id.startswith("saved-session-54321-")
    assert second.scope_id.startswith("saved-session-54322-")
    assert first.scope_id != second.scope_id

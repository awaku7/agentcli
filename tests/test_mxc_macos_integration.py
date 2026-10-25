"""Real Apple Silicon sandbox acceptance for every UAG entry-point scope.

This suite is opt-in and runs only on a macOS ARM64 GitHub Actions host.
"""

from __future__ import annotations

import json
import os
import platform
import re
import signal
import socket
import subprocess
import stat
import sys
import threading
import time

import pytest

from uagent.runtime.execution_broker import (
    IsolationLevel,
    SandboxCapability,
    SecurityProfile,
    TrustedSandboxScope,
    execution_profile,
    route_tool,
)
from uagent.runtime.mxc_backend import (
    MxcSessionManager,
    _workspace_for_scope,
    local_web_room_scope,
    startup_scope,
)
from uagent.runtime.runtime_init import capture_startup_uagent_env_snapshot

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin"
    or platform.machine().lower() not in {"arm64", "aarch64"}
    or os.environ.get("UAGENT_RUN_MXC_MACOS_INTEGRATION") != "1",
    reason="requires explicitly enabled Apple Silicon real-host Seatbelt integration",
)


@pytest.fixture(scope="module")
def backend():
    capture_startup_uagent_env_snapshot(force=True)
    manager, report = MxcSessionManager.initialize(allow_install=True)
    assert report.get("backend") == "seatbelt", report
    assert manager.capabilities.satisfies(
        minimum_isolation=IsolationLevel.CONTAINER,
        required=frozenset(SandboxCapability),
    )
    try:
        yield manager
    finally:
        manager.close_all()


def _assert_full_scope(manager, scope, tmp_path):
    manager.activate_scope(scope)
    try:
        with execution_profile(
            SecurityProfile.REMOTE,
            sandbox_enabled=True,
            scope=scope,
        ):
            decision = route_tool(
                "python_exec",
                {},
                profile=SecurityProfile.REMOTE,
                sandbox_enabled=True,
                backend_available=True,
                backend_capabilities=manager.capabilities,
                known_tool=True,
            )
            assert decision.allowed, decision
        created = manager.run_tool(
            scope,
            "create_file",
            {"filename": "hello.txt", "content": "macos-seatbelt"},
        )
        assert "sandbox error" not in created, created
        scope_workspace = _workspace_for_scope(scope)
        assert stat.S_IMODE(scope_workspace.stat().st_mode) == 0o700
        text = manager.run_tool(scope, "read_file", {"path": "hello.txt"})
        assert "macos-seatbelt" in text, text

        # Host canary and a host-side reachable listener MUST be denied.
        canary = tmp_path / "host-secret.txt"
        canary.write_text("host-secret", encoding="utf-8")
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        listener.settimeout(0.2)
        done = threading.Event()

        def accept():
            while not done.is_set():
                try:
                    connection, _ = listener.accept()
                except OSError:
                    continue
                else:
                    connection.close()

        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        try:
            with socket.create_connection(listener.getsockname(), timeout=2):
                pass
            code = (
                "import socket\n"
                "from pathlib import Path\n"
                f"canary = Path({str(canary)!r})\n"
                "try:\n"
                "    leaked = canary.read_text(encoding='utf-8')\n"
                "except OSError:\n"
                "    leaked = 'BLOCKED'\n"
                "sock = socket.socket()\n"
                f"rc = sock.connect_ex(('127.0.0.1', {listener.getsockname()[1]}))\n"
                "sock.close()\n"
                "print('FILE=' + leaked)\n"
                "print('LOOPBACK=' + str(rc))\n"
            )
            raw = manager.run_tool(scope, "python_exec", {"code": code})
            result = json.loads(raw)
            assert result["returncode"] == 0, result
            assert result["timeout"] is False, result
            assert "FILE=BLOCKED" in result["stdout"], result
            assert "LOOPBACK=0" not in result["stdout"], result
            assert "host-secret" not in result["stdout"], result
        finally:
            done.set()
            listener.close()
            thread.join(timeout=2)

        # Native SDK kill/wait must reap a child spawned inside python_exec.
        child_script = (
            "import pathlib,time\n"
            "p=pathlib.Path('child.txt')\n"
            "i=0\n"
            "while True:\n"
            "    temporary=p.with_suffix('.tmp')\n"
            "    temporary.write_text(str(i))\n"
            "    temporary.replace(p)\n"
            "    i += 1\n"
            "    time.sleep(0.05)\n"
        )
        child_code = (
            "import pathlib,subprocess,sys,time\n"
            f"subprocess.Popen([sys.executable, '-c', {child_script!r}])\n"
            "for _ in range(100):\n"
            "    p = pathlib.Path('child.txt')\n"
            "    if p.is_file() and p.read_text().strip().isdigit():\n"
            "        break\n"
            "    time.sleep(0.02)\n"
            "else:\n"
            "    raise RuntimeError('child did not write its ready marker')\n"
            "print('CHILD_READY')\n"
        )
        result = json.loads(
            manager.run_tool(scope, "python_exec", {"code": child_code})
        )
        assert result["returncode"] == 0, result
        assert "CHILD_READY" in result["stdout"], result
        first = manager.run_tool(scope, "read_file", {"path": "child.txt"})
        assert first.strip().isdigit(), f"child never executed: {first}"
        time.sleep(0.35)
        second = manager.run_tool(scope, "read_file", {"path": "child.txt"})
        assert second.strip().isdigit(), f"child file not readable: {second}"
        assert first == second, f"orphan MXC sandbox child: {first} -> {second}"
    finally:
        manager.close_scope(scope)


def test_macos_seatbelt_cli_gui_web_and_remote_a2a(backend, tmp_path):
    cli = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id="mac-cli-test",
    )
    _assert_full_scope(backend, cli, tmp_path)

    gui = startup_scope(
        entry_point="gui",
        project_path=str(tmp_path),
        session_id="mac-gui-test",
    )
    _assert_full_scope(backend, gui, tmp_path)

    web = local_web_room_scope(
        principal_id="mac-web-user",
        project_id="mac-web-project",
        room_id="mac-room",
        room_generation="mac-gen-1",
    )
    _assert_full_scope(backend, web, tmp_path)

    a2a = TrustedSandboxScope(
        deployment_id="a2a",
        principal_id="mac-a2a-user",
        project_id="mac-a2a-project",
        scope_kind="a2a-task",
        scope_id="mac-a2a-task",
    )
    _assert_full_scope(backend, a2a, tmp_path)


def test_macos_detached_python_child_does_not_outlive_one_shot_sandbox(
    backend, tmp_path
):
    """A new process group must not let a Python descendant escape SDK reaping."""
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id="mac-detached-test",
    )
    backend.activate_scope(scope)
    child_pid = None

    def child_running(pid: int) -> bool:
        proc = subprocess.run(
            ["/bin/ps", "-p", str(pid), "-o", "stat="],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        return proc.returncode == 0 and not proc.stdout.strip().startswith("Z")

    try:
        child_script = (
            "import pathlib,time\n"
            "p=pathlib.Path('detached-child.txt')\n"
            "i=0\n"
            "while True:\n"
            "    temporary=p.with_suffix('.tmp')\n"
            "    temporary.write_text(str(i))\n"
            "    temporary.replace(p)\n"
            "    i+=1\n"
            "    time.sleep(0.05)\n"
        )
        code = (
            "import pathlib,subprocess,sys,time\n"
            "child = subprocess.Popen([sys.executable, '-c', "
            f"{child_script!r}], start_new_session=True)\n"
            "for _ in range(100):\n"
            "    p=pathlib.Path('detached-child.txt')\n"
            "    if p.is_file() and p.read_text().strip().isdigit():\n"
            "        break\n"
            "    time.sleep(0.02)\n"
            "else:\n"
            "    raise RuntimeError('detached child did not execute')\n"
            "print('DETACHED_CHILD_READY')\n"
            "print('DETACHED_CHILD_PID=' + str(child.pid))\n"
        )
        result = json.loads(backend.run_tool(scope, "python_exec", {"code": code}))
        assert result["returncode"] == 0, result
        assert "DETACHED_CHILD_READY" in result["stdout"], result
        match = re.search(r"DETACHED_CHILD_PID=(\d+)", result["stdout"])
        assert match is not None, result
        child_pid = int(match.group(1))
        for _ in range(60):
            if not child_running(child_pid):
                break
            time.sleep(0.05)
        assert not child_running(
            child_pid
        ), f"MXC did not terminate its detached child PID {child_pid}"
        first = backend.run_tool(scope, "read_file", {"path": "detached-child.txt"})
        assert first.strip().isdigit(), first
        time.sleep(0.35)
        second = backend.run_tool(scope, "read_file", {"path": "detached-child.txt"})
        assert second.strip().isdigit(), second
        assert (
            first == second
        ), f"detached Python child survived MXC wait: {first} -> {second}"
    finally:
        if child_pid is not None and child_running(child_pid):
            os.kill(child_pid, signal.SIGKILL)
        backend.close_scope(scope)



def test_macos_denies_workspace_escape_and_unlisted_tools(backend, tmp_path):
    """Exercise unsafe requests through the real UAG manager, not a mock."""
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id="mac-negative-operations",
    )
    backend.activate_scope(scope)
    canary = tmp_path / "outside-canary.txt"
    canary.write_text("unchanged-on-host", encoding="utf-8")
    try:
        created = backend.run_tool(
            scope,
            "create_file",
            {"filename": "inside.txt", "content": "inside"},
        )
        assert "Created" in created, created

        for name, args in (
            ("create_file", {"filename": "../outside-canary.txt", "content": "BAD"}),
            ("create_file", {"filename": str(canary), "content": "BAD"}),
            ("read_file", {"path": str(canary)}),
            ("file_exists", {"path": "../outside-canary.txt"}),
        ):
            denied = backend.run_tool(scope, name, args)
            assert denied.startswith("[sandbox error]"), (name, args, denied)

        with pytest.raises(PermissionError):
            backend.run_tool(scope, "cmd_exec", {"command": "echo forbidden"})

        workspace = _workspace_for_scope(scope)
        (workspace / "host-link").symlink_to(canary)
        denied = backend.run_tool(scope, "read_file", {"path": "host-link"})
        assert denied.startswith("[sandbox error]"), denied

        # A confined Python process must be unable to change a file in a
        # writable host directory that was not granted to the sandbox.
        code = (
            "from pathlib import Path\n"
            f"canary = Path({str(canary)!r})\n"
            "try:\n"
            "    canary.write_text('ESCAPED', encoding='utf-8')\n"
            "except OSError:\n"
            "    print('HOST_WRITE_BLOCKED')\n"
            "else:\n"
            "    print('HOST_WRITE_ALLOWED')\n"
        )
        result = json.loads(backend.run_tool(scope, "python_exec", {"code": code}))
        assert result["returncode"] == 0, result
        assert result["timeout"] is False, result
        assert "HOST_WRITE_BLOCKED" in result["stdout"], result
        assert "HOST_WRITE_ALLOWED" not in result["stdout"], result
        assert canary.read_text(encoding="utf-8") == "unchanged-on-host"
    finally:
        backend.close_scope(scope)


def test_macos_workspace_cannot_cross_cli_and_web_scopes(backend, tmp_path):
    """Different entrypoints use distinct, inaccessible workspace roots."""
    cli = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id="mac-cross-scope-cli",
    )
    web = local_web_room_scope(
        principal_id="mac-other-principal",
        project_id="mac-other-project",
        room_id="mac-cross-scope-room",
        room_generation="mac-other-generation",
    )
    assert _workspace_for_scope(cli) != _workspace_for_scope(web)
    backend.activate_scope(cli)
    backend.activate_scope(web)
    try:
        created = backend.run_tool(
            cli,
            "create_file",
            {"filename": "private-marker.txt", "content": "CLI_ONLY_SECRET"},
        )
        assert "Created" in created, created
        other = backend.run_tool(web, "file_exists", {"path": "private-marker.txt"})
        assert json.loads(other)["exists"] is False, other

        code = (
            "from pathlib import Path\n"
            f"p = Path({str(_workspace_for_scope(cli) / 'private-marker.txt')!r})\n"
            "try:\n"
            "    data = p.read_text(encoding='utf-8')\n"
            "except OSError:\n"
            "    print('OTHER_SCOPE_BLOCKED')\n"
            "else:\n"
            "    print('OTHER_SCOPE_READ=' + data)\n"
        )
        result = json.loads(backend.run_tool(web, "python_exec", {"code": code}))
        assert result["returncode"] == 0, result
        assert "OTHER_SCOPE_BLOCKED" in result["stdout"], result
        assert "CLI_ONLY_SECRET" not in result["stdout"], result
    finally:
        backend.close_scope(web)
        backend.close_scope(cli)


def test_macos_remote_vm_requirement_remains_fail_closed(backend, tmp_path, monkeypatch):
    """VM-required Remote requests must not be downgraded to Seatbelt."""
    scope = TrustedSandboxScope(
        deployment_id="a2a",
        principal_id="mac-vm-required-user",
        project_id="mac-vm-required-project",
        scope_kind="a2a-task",
        scope_id="mac-vm-required-operation",
    )
    monkeypatch.setenv("UAGENT_REMOTE_SANDBOX_MIN_ISOLATION", "vm")
    with execution_profile(SecurityProfile.REMOTE, sandbox_enabled=True, scope=scope):
        decision = route_tool(
            "python_exec",
            {},
            profile=SecurityProfile.REMOTE,
            sandbox_enabled=True,
            backend_available=True,
            backend_capabilities=backend.capabilities,
            known_tool=True,
        )
        assert not decision.allowed, decision
        assert "capabilities" in decision.reason or "acceptance" in decision.reason

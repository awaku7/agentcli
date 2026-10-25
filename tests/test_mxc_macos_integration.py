"""Real Apple Silicon sandbox acceptance for every UAG entry-point scope.

This suite is opt-in and runs only on a macOS ARM64 GitHub Actions host.
"""

from __future__ import annotations

import json
import os
import platform
import socket
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
            "import pathlib,time\\n"
            "p=pathlib.Path('child.txt')\\n"
            "i=0\\n"
            "while True:\\n"
            "    p.write_text(str(i))\\n"
            "    i += 1\\n"
            "    time.sleep(0.05)\\n"
        )
        child_code = (
            "import subprocess,sys,time\\n"
            f"subprocess.Popen([sys.executable, '-c', {child_script!r}])\\n"
            "time.sleep(0.2)\\n"
            "print('SPAWNED')\\n"
        )
        result = json.loads(
            manager.run_tool(scope, "python_exec", {"code": child_code})
        )
        assert result["returncode"] == 0, result
        assert "SPAWNED" in result["stdout"], result
        first = manager.run_tool(scope, "read_file", {"path": "child.txt"})
        time.sleep(0.35)
        second = manager.run_tool(scope, "read_file", {"path": "child.txt"})
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

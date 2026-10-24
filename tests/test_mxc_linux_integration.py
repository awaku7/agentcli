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

from uagent.runtime.mxc_backend import (
    MxcSessionManager,
    _workspace_for_scope,
    startup_scope,
)

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux")
    or platform.machine().lower() not in {"x86_64", "amd64"}
    or os.environ.get("UAGENT_RUN_MXC_LINUX_INTEGRATION") != "1",
    reason="requires an explicitly enabled Ubuntu x86_64 MXC/Bubblewrap integration run",
)


def _python_result(manager: MxcSessionManager, scope, code: str) -> dict:
    result = manager.run_tool(scope, "python_exec", {"code": code})
    return json.loads(result)


def test_linux_mxc_bubblewrap_denies_host_file_and_loopback_and_reaps_children(
    tmp_path,
):
    canary = tmp_path / "host-canary.txt"
    canary.write_text("host-secret", encoding="utf-8")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(0.2)
    stop_listener = threading.Event()

    def accept_once():
        while not stop_listener.is_set():
            try:
                connection, _ = listener.accept()
            except (TimeoutError, OSError):
                continue
            else:
                connection.close()

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()
    manager, report = MxcSessionManager.initialize(allow_install=False)
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id=f"linux-mxc-{os.getpid()}-{time.time_ns()}",
    )
    manager.activate_scope(scope)
    try:
        port = listener.getsockname()[1]
        code = (
            "import socket\n"
            "from pathlib import Path\n"
            f"canary = Path({str(canary)!r})\n"
            "try:\n"
            "    leaked = canary.read_text(encoding='utf-8')\n"
            "except (OSError, PermissionError):\n"
            "    leaked = 'BLOCKED'\n"
            "sock = socket.socket()\n"
            f"connect_result = sock.connect_ex(('127.0.0.1', {port}))\n"
            "sock.close()\n"
            "print('FILE=' + leaked)\n"
            "print('LOOPBACK=' + str(connect_result))\n"
        )
        result = _python_result(manager, scope, code)
        workspace = _workspace_for_scope(scope)
        assert stat.S_IMODE(workspace.stat().st_mode) == 0o700
        assert stat.S_IMODE((workspace / ".home").stat().st_mode) == 0o700
        assert stat.S_IMODE((workspace / ".temp").stat().st_mode) == 0o700
        assert result["returncode"] == 0, result
        assert "FILE=BLOCKED" in result["stdout"], result
        assert "LOOPBACK=0" not in result["stdout"], result
        assert report.get("backend") == "bubblewrap", report

        child_marker = "linux-mxc-child-marker.txt"
        child_script = (
            "import pathlib, time\n"
            f"path = pathlib.Path({child_marker!r})\n"
            "count = 0\n"
            "while True:\n"
            "    path.write_text(str(count))\n"
            "    count += 1\n"
            "    time.sleep(0.05)\n"
        )
        child_code = (
            "import subprocess, sys, time\n"
            f"child = subprocess.Popen([sys.executable, '-c', {child_script!r}])\n"
            "time.sleep(0.2)\n"
            "print('CHILD=' + str(child.pid))\n"
        )
        child_result = _python_result(manager, scope, child_code)
        assert child_result["returncode"] == 0, child_result
        first = manager.run_tool(scope, "read_file", {"path": child_marker})
        time.sleep(0.3)
        second = manager.run_tool(scope, "read_file", {"path": child_marker})
        assert (
            first == second
        ), f"sandbox child continued after its MXC container exited: {first} -> {second}"
    finally:
        manager.close_scope(scope)
        manager.close_all()
        stop_listener.set()
        listener.close()
        thread.join(timeout=1)

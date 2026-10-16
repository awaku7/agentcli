from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time

import pytest

from uagent.runtime.mxc_backend import MxcSessionManager, startup_scope

pytestmark = pytest.mark.skipif(
    os.name != "nt" or os.environ.get("UAGENT_RUN_MXC_INTEGRATION") != "1",
    reason="requires an explicitly enabled Windows MXC host integration run",
)


def _run_python(manager, scope, code: str) -> dict:
    raw = manager.run_tool(scope, "python_exec", {"code": code})
    return json.loads(raw)


def _pid_is_alive(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist.exe", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        shell=False,
    )
    return str(pid) in result.stdout


def _process_with_command_marker_is_alive(marker: str) -> bool:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    powershell = os.path.join(
        system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
    )
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$marker = '{marker}'; "
        "$found = Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" "
        "| Where-Object { $_.CommandLine -and $_.CommandLine.Contains($marker) }; "
        "if ($found) { Write-Output 'ALIVE' } else { Write-Output 'DEAD' }"
    )
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        shell=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip() == "ALIVE"


def test_mxc_python_os_exit_fails_closed_and_reaps_children(tmp_path):
    manager, _report = MxcSessionManager.initialize(allow_install=False)
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id=f"pytest-os-exit-{os.getpid()}-{time.time_ns()}",
    )
    marker = f"UAG_MXC_ABRUPT_EXIT_{time.time_ns()}"
    child_code = (
        "import time\n"
        "from pathlib import Path\n"
        f"print({marker!r}, flush=True)\n"
        "path = Path('orphan-child-state.txt')\n"
        "count = 0\n"
        "while True:\n"
        "    path.write_text(str(count))\n"
        "    count += 1\n"
        "    time.sleep(0.05)\n"
    )
    code = (
        "import os, subprocess, sys"
        + chr(10)
        + f"subprocess.Popen([sys.executable, '-I', '-X', 'utf8', '-c', {child_code!r}])"
        + chr(10)
        + "os._exit(0)"
        + chr(10)
    )
    try:
        result = manager.run_tool(scope, "python_exec", {"code": code})
        assert "exited before its completion marker" in result.lower()
        assert len(manager._sessions) == 1
        deadline = time.monotonic() + 5
        while (
            _process_with_command_marker_is_alive(marker)
            and time.monotonic() < deadline
        ):
            time.sleep(0.1)
        assert not _process_with_command_marker_is_alive(marker)
    finally:
        manager.close_scope(scope)
        manager.close_all()


def test_mxc_os_exit_cannot_bypass_workspace_quota(tmp_path):
    manager, _report = MxcSessionManager.initialize(allow_install=False)
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id=f"pytest-os-exit-quota-{os.getpid()}-{time.time_ns()}",
    )
    code = (
        "import os\n"
        "with open('oversized-on-exit.bin', 'wb') as stream:\n"
        "    stream.truncate(256 * 1024 * 1024 + 1)\n"
        "os._exit(0)\n"
    )
    try:
        result = manager.run_tool(scope, "python_exec", {"code": code})
        assert "workspace limit exceeded" in result.lower()
    finally:
        manager.close_scope(scope)
        manager.close_all()


def test_mxc_workspace_scan_tolerates_concurrent_file_deletions(tmp_path):
    manager, _report = MxcSessionManager.initialize(allow_install=False)
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id=f"pytest-delete-race-{os.getpid()}-{time.time_ns()}",
    )
    try:
        result = _run_python(
            manager,
            scope,
            "import time\n"
            "from pathlib import Path\n"
            "root = Path('delete-race')\n"
            "root.mkdir()\n"
            "deadline = time.monotonic() + 3\n"
            "count = 0\n"
            "while time.monotonic() < deadline:\n"
            "    item = root / f'{count}.bin'\n"
            "    item.write_bytes(b'x')\n"
            "    item.unlink()\n"
            "    count += 1\n"
            "print('DELETE_RACE_COMPLETED', count)\n",
        )
        assert result["returncode"] == 0
        assert "DELETE_RACE_COMPLETED" in result["stdout"]
    finally:
        manager.close_scope(scope)
        manager.close_all()


def test_mxc_close_removes_readonly_workspace_entries(tmp_path):
    manager, _report = MxcSessionManager.initialize(allow_install=False)
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id=f"pytest-readonly-{os.getpid()}-{time.time_ns()}",
    )
    try:
        result = _run_python(
            manager,
            scope,
            "from pathlib import Path\n"
            "read_only = Path('read-only.txt')\n"
            "read_only.write_text('protected')\n"
            "read_only.chmod(0o444)\n",
        )
        assert result["returncode"] == 0
        workspace = next(iter(manager._sessions.values())).workspace
        manager.close_scope(scope)
        assert not workspace.exists()

        assert (
            manager.run_tool(
                scope,
                "create_file",
                {"filename": "fresh.txt", "content": "ready"},
            )
            == "Created fresh.txt"
        )
    finally:
        manager.close_scope(scope)
        manager.close_all()


def test_mxc_python_waits_for_atexit_handlers(tmp_path):
    manager, _report = MxcSessionManager.initialize(allow_install=False)
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id=f"pytest-atexit-{os.getpid()}-{time.time_ns()}",
    )
    try:
        result = _run_python(
            manager,
            scope,
            "import atexit\n"
            "from pathlib import Path\n"
            "atexit.register(lambda: Path('atexit-result.txt').write_text('finished'))\n"
            "print('script finished')\n",
        )
        assert result["returncode"] == 0
        assert (
            manager.run_tool(scope, "read_file", {"path": "atexit-result.txt"})
            == "finished"
        )
    finally:
        manager.close_scope(scope)
        manager.close_all()


def test_mxc_windows_session_isolation_and_cleanup(tmp_path):
    manager, _report = MxcSessionManager.initialize(allow_install=False)
    scope = startup_scope(
        entry_point="cli",
        project_path=str(tmp_path),
        session_id=f"pytest-{os.getpid()}-{time.time_ns()}",
    )
    secret = tmp_path / "host-secret.txt"
    secret.write_text("MXC_HOST_SECRET_CANARY", encoding="utf-8")
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(0.5)
    accepted: list[bool] = []

    def accept_once():
        try:
            conn, _ = server.accept()
            accepted.append(True)
            conn.close()
        except OSError:
            pass

    accept_thread = threading.Thread(target=accept_once, daemon=True)
    accept_thread.start()
    try:
        assert (
            manager.run_tool(
                scope,
                "create_file",
                {"filename": "session.txt", "content": "same-session"},
            )
            == "Created session.txt"
        )

        python_result = _run_python(
            manager,
            scope,
            "from pathlib import Path\n"
            "Path('result.txt').write_text(Path('session.txt').read_text() + '-python')\n"
            "print(Path('result.txt').read_text())\n",
        )
        assert python_result["returncode"] == 0
        assert "same-session-python" in python_result["stdout"]
        assert (
            manager.run_tool(scope, "read_file", {"path": "result.txt"})
            == "same-session-python"
        )
        assert len(manager._sessions) == 1

        other_scope = startup_scope(
            entry_point="cli",
            project_path=str(tmp_path),
            session_id=f"pytest-other-{os.getpid()}-{time.time_ns()}",
        )
        other_session = json.loads(
            manager.run_tool(other_scope, "file_exists", {"path": "session.txt"})
        )
        assert other_session["exists"] is False

        directory_ads_result = manager.run_tool(
            other_scope,
            "python_exec",
            {
                "code": (
                    "from pathlib import Path\n"
                    "Path('carrier_dir').mkdir()\n"
                    "with open('carrier_dir:payload', 'wb') as f: f.truncate(256 * 1024 * 1024 + 1)\n"
                )
            },
        )
        assert "workspace limit exceeded" in directory_ads_result.lower()

        secret_result = _run_python(
            manager,
            scope,
            "from pathlib import Path\n"
            f"p = Path({str(secret)!r})\n"
            "try:\n"
            "    print('LEAK', p.read_text())\n"
            "except Exception as exc:\n"
            "    print('BLOCKED', type(exc).__name__)\n",
        )
        assert "BLOCKED" in secret_result["stdout"]
        assert "MXC_HOST_SECRET_CANARY" not in secret_result["stdout"]

        port = server.getsockname()[1]
        network_result = _run_python(
            manager,
            scope,
            "import socket\n"
            f"try:\n    socket.create_connection(('127.0.0.1', {port}), timeout=1)\n"
            "    print('LOOPBACK_REACHED')\n"
            "except Exception as exc:\n"
            "    print('BLOCKED', type(exc).__name__)\n",
        )
        assert "BLOCKED" in network_result["stdout"]
        assert "LOOPBACK_REACHED" not in network_result["stdout"]
        accept_thread.join(timeout=1)
        assert accepted == []

        child_result = _run_python(
            manager,
            scope,
            "import subprocess, sys\n"
            "child = subprocess.Popen([sys.executable, '-I', '-X', 'utf8', '-c', 'import time; time.sleep(300)'])\n"
            "print(child.pid)\n",
        )
        child_pid = int(child_result["stdout"].strip().splitlines()[-1])
        deadline = time.monotonic() + 5
        while _pid_is_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _pid_is_alive(child_pid)

        ads_quota_result = manager.run_tool(
            scope,
            "python_exec",
            {
                "code": (
                    "with open('carrier', 'wb') as f: f.write(b'x')\n"
                    "with open('carrier:payload', 'wb') as f: f.truncate(256 * 1024 * 1024 + 1)\n"
                )
            },
        )
        assert "workspace limit exceeded" in ads_quota_result.lower()

        quota_result = manager.run_tool(
            scope,
            "python_exec",
            {
                "code": (
                    "with open('oversized.bin', 'wb') as f: f.truncate(256 * 1024 * 1024 + 1)\n"
                )
            },
        )
        assert "workspace limit exceeded" in quota_result.lower()

        timeout_result = _run_python(manager, scope, "import time; time.sleep(45)")
        assert timeout_result["timeout"] is True
    finally:
        manager.close_scope(scope)
        manager.close_all()
        server.close()

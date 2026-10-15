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

        timeout_result = _run_python(manager, scope, "import time; time.sleep(45)")
        assert timeout_result["timeout"] is True
    finally:
        manager.close_scope(scope)
        manager.close_all()
        server.close()

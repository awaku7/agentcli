"""run_interruptible: subprocess waits that honour the interrupt flag."""

from __future__ import annotations

import subprocess
import sys
import threading
import time

import pytest

from uagent import core
from uagent.tools import safe_exec_ops


@pytest.fixture(autouse=True)
def _reset_interrupt_flag():
    with core.interrupt_lock:
        core.interrupt_requested = False
    yield
    with core.interrupt_lock:
        core.interrupt_requested = False


def _set_interrupt_flag() -> None:
    with core.interrupt_lock:
        core.interrupt_requested = True


def test_runs_to_completion_like_subprocess_run():
    proc = safe_exec_ops.run_interruptible(
        args=[sys.executable, "-c", "print('hello')"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30.0,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "hello"


def test_timeout_still_raises_timeout_expired():
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        safe_exec_ops.run_interruptible(
            args=[sys.executable, "-c", "import time; time.sleep(30)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=0.5,
        )
    assert time.monotonic() - started < 10.0


def test_interrupt_terminates_descendants_too(tmp_path):
    # Regression: killing only the shell would leave the programs it
    # launched running; a cancelled command must not keep modifying
    # files alongside the next turn. The descendant writes a marker
    # file 1.5s in; the interrupt lands at 0.4s, so the marker must
    # never appear.
    marker = tmp_path / "descendant-wrote.txt"
    child_code = (
        "import time, pathlib\n"
        "time.sleep(1.5)\n"
        f"pathlib.Path({str(marker)!r}).write_text('x')\n"
    )
    parent_code = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "time.sleep(30)\n"
    )
    timer = threading.Timer(0.4, _set_interrupt_flag)
    timer.start()
    try:
        with pytest.raises(safe_exec_ops.SubprocessInterrupted):
            safe_exec_ops.run_interruptible(
                args=[sys.executable, "-c", parent_code],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60.0,
            )
    finally:
        timer.cancel()
    time.sleep(2.5)
    assert not marker.exists()


def test_interrupt_flag_kills_the_child_and_raises():
    timer = threading.Timer(0.4, _set_interrupt_flag)
    started = time.monotonic()
    timer.start()
    try:
        with pytest.raises(safe_exec_ops.SubprocessInterrupted):
            safe_exec_ops.run_interruptible(
                args=[sys.executable, "-c", "import time; time.sleep(30)"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60.0,
            )
    finally:
        timer.cancel()
    assert time.monotonic() - started < 10.0

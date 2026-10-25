"""Bounded macOS ARM64 MXC host helper for shared CLI, GUI, Web, and A2A.

This host watchdog is a soft resource guard, NOT a cgroup or Windows Job
Object. Remote and local entrypoints use the same backend and must pass the
same host capability probe; a stronger VM tier remains unavailable. Native
Seatbelt isolation is enforced independently by MXC-spawned processes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from pathlib import Path

MEMORY_LIMIT_KIB = 1_048_576
PROCESS_LIMIT = 64
CPU_LIMIT_SECONDS = 4 * 60 * 60
INTERVAL_SECONDS = 0.5


def _cpu_seconds(value: str) -> float:
    days = 0
    if "-" in value:
        days_text, value = value.split("-", 1)
        days = int(days_text)
    fields = [float(part) for part in value.split(":")]
    if len(fields) == 3:
        hours, minutes, seconds = fields
    elif len(fields) == 2:
        hours, minutes, seconds = 0, fields[0], fields[1]
    else:
        raise RuntimeError("unrecognized macOS process CPU time")
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _group_usage(pgid: int) -> tuple[int, int, float]:
    report = subprocess.run(
        ["/bin/ps", "-axo", "pgid=,rss=,time=,stat="],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    count, rss_kib, cpu = 0, 0, 0.0
    for line in report.stdout.splitlines():
        parts = line.split()
        if len(parts) != 4 or int(parts[0]) != pgid:
            continue
        # Reaped-but-not-yet-collected zombies consume no active resources.
        if "Z" in parts[3]:
            continue
        count += 1
        rss_kib += int(parts[1])
        cpu += _cpu_seconds(parts[2])
    return count, rss_kib, cpu


class MacosProcessGroup:
    """Owned private POSIX session with verified group cleanup and soft quotas."""

    def __init__(self, process: subprocess.Popen):
        self.process = process
        self.pgid = process.pid
        self.error: str | None = None
        self._stop = threading.Event()
        self._watcher = threading.Thread(
            target=self._watch, daemon=True, name="mxc-macos-quota"
        )
        self._watcher.start()

    @classmethod
    def launch(cls, command: list[str], *, cwd: Path, env: dict[str, str]):
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            shell=False,
            env=env,
            start_new_session=True,
        )
        try:
            if os.getpgid(process.pid) != process.pid:
                raise RuntimeError("macOS MXC process group was not isolated")
            return cls(process)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            raise

    def _watch(self) -> None:
        while not self._stop.is_set():
            try:
                count, rss, cpu = _group_usage(self.pgid)
                if count > PROCESS_LIMIT:
                    raise RuntimeError("macOS MXC process group task limit exceeded")
                if rss > MEMORY_LIMIT_KIB:
                    raise RuntimeError("macOS MXC process group memory budget exceeded")
                if cpu > CPU_LIMIT_SECONDS:
                    raise RuntimeError("macOS MXC process group CPU budget exceeded")
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                try:
                    os.killpg(self.pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return
            self._stop.wait(INTERVAL_SECONDS)

    def close(self) -> None:
        self._stop.set()
        try:
            os.killpg(self.pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            raise RuntimeError("macOS MXC adapter did not stop") from None
        self._watcher.join(timeout=6)
        if self._watcher.is_alive():
            raise RuntimeError("macOS MXC quota watchdog did not stop")
        count, _rss, _cpu = _group_usage(self.pgid)
        if count:
            raise RuntimeError("macOS MXC process group cleanup is unverified")
        if self.error:
            raise RuntimeError(f"macOS MXC quota watcher failed closed: {self.error}")

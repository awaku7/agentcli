"""macOS ARM64 MXC host helper lifecycle and monitored resource bounds.

CLI, GUI, Web and A2A share this supervisor. Its resource monitoring is
sampled and is not a hard cgroup/Job Object equivalent. MXC Seatbelt is the
kernel-enforced boundary for the individual tool processes. Unverified child
cleanup must never release a workspace lease.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

MEMORY_LIMIT_KIB = 1_048_576
PROCESS_LIMIT = 64
CPU_LIMIT_SECONDS = 4 * 60 * 60
INTERVAL_SECONDS = 0.15


@dataclass(frozen=True)
class _Process:
    pid: int
    ppid: int
    pgid: int
    rss_kib: int
    cpu_seconds: float
    state: str
    started: str


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


def _process_table() -> dict[int, _Process]:
    report = subprocess.run(
        ["/bin/ps", "-axo", "pid=,ppid=,pgid=,rss=,time=,stat=,lstart="],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    result: dict[int, _Process] = {}
    for line in report.stdout.splitlines():
        parts = line.split(maxsplit=6)
        if len(parts) != 7:
            continue
        try:
            pid, ppid, pgid, rss = (int(v) for v in parts[:4])
            cpu = _cpu_seconds(parts[4])
        except ValueError as exc:
            raise RuntimeError("invalid macOS process accounting output") from exc
        result[pid] = _Process(
            pid=pid,
            ppid=ppid,
            pgid=pgid,
            rss_kib=rss,
            cpu_seconds=cpu,
            state=parts[5],
            started=parts[6],
        )
    return result


def _summarize(
    root_pid: int,
    group_id: int,
    known: dict[int, str],
    cpu_ledger: dict[tuple[int, str], float],
    table: dict[int, _Process],
) -> tuple[int, int, float]:
    """Track observed descendants even if they switch process groups.

    Keep each observed process' CPU high-water mark after it exits. A process
    that lived entirely between samples remains unobserved; this is explicitly
    NOT a hard aggregate CPU guarantee.
    """
    active = {
        pid
        for pid, row in table.items()
        if row.pgid == group_id or (pid in known and known[pid] == row.started)
    }
    root = table.get(root_pid)
    if root is not None and (root_pid not in known or known[root_pid] == root.started):
        active.add(root_pid)
    changed = True
    while changed:
        size = len(active)
        active.update(
            pid for pid, row in table.items() if row.ppid in active
        )
        changed = len(active) != size
    for pid in active:
        row = table[pid]
        previous = known.get(pid)
        if previous is not None and previous != row.started:
            # A recycled PID is not evidence that the old process survived.
            continue
        known[pid] = row.started
        key = (pid, row.started)
        cpu_ledger[key] = max(cpu_ledger.get(key, 0.0), row.cpu_seconds)
    valid = [
        row
        for pid, row in table.items()
        if known.get(pid) == row.started and "Z" not in row.state
    ]
    return (
        len(valid),
        sum(row.rss_kib for row in valid),
        sum(cpu_ledger.values()),
    )


class MacosProcessGroup:
    """Supervise the host helper plus observed descendants across PGID changes."""

    def __init__(self, process: subprocess.Popen):
        self.process = process
        self.pgid = process.pid
        self.error: str | None = None
        self._stop = threading.Event()
        self._known: dict[int, str] = {}
        self._cpu_ledger: dict[tuple[int, str], float] = {}
        self._started = time.monotonic()
        self._inspect()
        if process.pid not in self._known:
            raise RuntimeError("macOS MXC helper exited before process supervision")
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

    def _inspect(self) -> tuple[int, int, float]:
        return _summarize(
            self.process.pid,
            self.pgid,
            self._known,
            self._cpu_ledger,
            _process_table(),
        )

    def snapshot(self) -> frozenset[tuple[int, str]]:
        """Snapshot pre-existing persistent worker PIDs before one-shot tools."""
        self._inspect()
        table = _process_table()
        return frozenset(
            (pid, row.started)
            for pid, row in table.items()
            if self._known.get(pid) == row.started
        )

    def reap_since(self, baseline: frozenset[tuple[int, str]]) -> None:
        """Reap observed ephemeral tool descendants, including setsid children.

        The persistent worker was present in baseline and must stay alive.
        Any uncertain child state is an error: callers terminate the session
        and retain its workspace lease rather than returning success.
        """
        for attempt in range(12):
            self._inspect()
            table = _process_table()
            fresh = [
                row
                for pid, row in table.items()
                if self._known.get(pid) == row.started
                and (pid, row.started) not in baseline
                and "Z" not in row.state
            ]
            if not fresh:
                return
            for row in fresh:
                try:
                    os.kill(row.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            time.sleep(0.08)
        raise RuntimeError(
            "macOS MXC detached tool subprocess cleanup could not be verified"
        )

    def _terminate_observed(self) -> None:
        # Use the process start identity to avoid killing a reused PID.
        table = _process_table()
        _summarize(self.process.pid, self.pgid, self._known, self._cpu_ledger, table)
        try:
            os.killpg(self.pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for pid, started in list(self._known.items()):
            row = table.get(pid)
            if row is None or row.started != started:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def _watch(self) -> None:
        while not self._stop.is_set():
            try:
                count, rss, cpu = self._inspect()
                if count > PROCESS_LIMIT:
                    raise RuntimeError("macOS MXC observed process count exceeded")
                if rss > MEMORY_LIMIT_KIB:
                    raise RuntimeError("macOS MXC observed process RSS exceeded")
                if cpu > CPU_LIMIT_SECONDS:
                    raise RuntimeError("macOS MXC observed cumulative CPU exceeded")
                if time.monotonic() - self._started > CPU_LIMIT_SECONDS:
                    raise RuntimeError("macOS MXC maximum session duration exceeded")
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                try:
                    self._terminate_observed()
                except Exception:
                    pass
                return
            self._stop.wait(INTERVAL_SECONDS)

    def close(self) -> None:
        self._stop.set()
        self._watcher.join(timeout=7)
        if self._watcher.is_alive():
            raise RuntimeError("macOS MXC quota watchdog did not stop")
        self._terminate_observed()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("macOS MXC adapter did not stop") from exc
        # Recheck after killing the entire recorded lineage, including any
        # group-escaped children. Never release a lease if cleanup is unknown.
        for _ in range(5):
            count, _rss, _cpu = self._inspect()
            if not count:
                break
            self._terminate_observed()
            time.sleep(0.1)
        else:
            raise RuntimeError("macOS MXC descendant cleanup could not be verified")
        if self.error:
            raise RuntimeError(f"macOS MXC host watchdog failed closed: {self.error}")

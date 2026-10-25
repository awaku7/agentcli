"""Fail-closed Linux host resource scope for MXC worker processes.

MXC/Bubblewrap isolates the workload. This module puts the trusted MXC Node
adapter and all of its descendants in a per-user systemd cgroup so aggregate
memory, task-count, CPU-time, and process-tree cleanup are enforced by the host.
It requires cgroup v2 and a working systemd user manager; there is no fallback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

MEMORY_LIMIT_BYTES = 1_073_741_824
TASK_LIMIT = 64
CPU_BUDGET_NS = 4 * 60 * 60 * 1_000_000_000
CPU_POLL_INTERVAL_SECONDS = 0.5
START_TIMEOUT_SECONDS = 10
STOP_TIMEOUT_SECONDS = 10
CGROUP_ROOT = Path("/sys/fs/cgroup")
_UNREAPED_SCOPES: list["LinuxSystemdScope"] = []


class LinuxScopeCleanupError(RuntimeError):
    """Raised when a started scope cannot be proven empty after cleanup."""

    def __init__(self, message: str, scope: "LinuxSystemdScope") -> None:
        super().__init__(message)
        self.scope = scope


def _system_binary(name: str) -> str:
    path = shutil.which(name, path=os.defpath)
    if not path:
        raise RuntimeError(f"Linux MXC requires the system '{name}' executable")
    return str(Path(path).resolve())


def _user_bus_environment() -> dict[str, str]:
    """Construct the per-user systemd connection without trusting project dotenv."""
    try:
        import pwd

        uid = os.getuid()
        account = pwd.getpwuid(uid)
    except (AttributeError, KeyError, OSError) as exc:
        raise RuntimeError("Linux MXC requires a local Unix user account") from exc
    runtime_dir = Path(f"/run/user/{uid}")
    bus = runtime_dir / "bus"
    if not runtime_dir.is_dir() or not bus.exists():
        raise RuntimeError(
            "Linux MXC requires an active systemd user manager and D-Bus at "
            f"{bus}; no root or host-execution fallback is permitted"
        )
    return {
        "HOME": account.pw_dir,
        "USER": account.pw_name,
        "LOGNAME": account.pw_name,
        "XDG_RUNTIME_DIR": str(runtime_dir),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={bus}",
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
    }


def _parse_bytes(value: str) -> int | None:
    value = value.strip().lower()
    if value in {"", "infinity", "max"}:
        return None
    multipliers = {"k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}
    try:
        if value[-1:] in multipliers:
            return int(float(value[:-1]) * multipliers[value[-1]])
        return int(value)
    except (ValueError, IndexError):
        return None


def _parse_systemd_duration_us(value: str) -> int | None:
    value = value.strip().lower()
    multipliers = {
        "usec": 1,
        "us": 1,
        "msec": 1_000,
        "ms": 1_000,
        "sec": 1_000_000,
        "s": 1_000_000,
        "min": 60_000_000,
        "h": 3_600_000_000,
    }
    for suffix, multiplier in multipliers.items():
        if value.endswith(suffix):
            try:
                return int(float(value[: -len(suffix)]) * multiplier)
            except ValueError:
                return None
    try:
        return int(value)
    except ValueError:
        return None


def systemd_scope_command(systemd_run: str, unit: str, command: list[str]) -> list[str]:
    """Return the auditable, no-shell command used to create an MXC scope."""
    return [
        systemd_run,
        "--user",
        "--scope",
        "--quiet",
        f"--unit={unit}",
        f"--property=MemoryMax={MEMORY_LIMIT_BYTES}",
        "--property=MemorySwapMax=0",
        f"--property=TasksMax={TASK_LIMIT}",
        "--property=CPUAccounting=yes",
        "--property=CPUQuota=100%",
        "--",
        *command,
    ]


class LinuxSystemdScope:
    """Run one MXC adapter in a resource-limited, killable user scope."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        *,
        unit: str,
        environment: dict[str, str],
        systemctl: str,
    ) -> None:
        self.process = process
        self.unit = unit
        self.environment = environment
        self.systemctl = systemctl
        self._lock = threading.RLock()
        self._closed = False
        self._cpu_exceeded = False
        self._watchdog_error: str | None = None
        self._cgroup_path: Path | None = None
        self._monitor_stop = threading.Event()
        self._monitor = threading.Thread(
            target=self._monitor_cpu,
            name=f"mxc-cpu-watch-{unit}",
            daemon=True,
        )

    @classmethod
    def launch(
        cls,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        unit_prefix: str = "uagent-mxc",
        unit: str | None = None,
    ) -> "LinuxSystemdScope":
        if not command or any(not isinstance(item, str) for item in command):
            raise ValueError("MXC scoped command must be a non-empty string list")
        if not Path(cwd).is_absolute():
            raise ValueError("MXC scope working directory must be absolute")
        if not sys_platform_linux():
            raise RuntimeError("Linux MXC systemd scopes are only available on Linux")
        if (
            not CGROUP_ROOT.is_dir()
            or not (CGROUP_ROOT / "cgroup.controllers").is_file()
        ):
            raise RuntimeError("Linux MXC requires a mounted cgroup v2 hierarchy")
        controllers = set(
            (CGROUP_ROOT / "cgroup.controllers").read_text(encoding="ascii").split()
        )
        if not {"cpu", "memory", "pids"}.issubset(controllers):
            raise RuntimeError(
                "Linux MXC requires cgroup v2 cpu, memory, and pids controllers"
            )

        systemd_run = _system_binary("systemd-run")
        systemctl = _system_binary("systemctl")
        bus_env = _user_bus_environment()
        # Only the systemd connection comes from the OS account. Do not allow
        # project dotenv to select the host command PATH, home, or D-Bus socket.
        safe_env = {
            **bus_env,
            **{
                key: value
                for key, value in env.items()
                if key
                not in {
                    "PATH",
                    "HOME",
                    "USER",
                    "LOGNAME",
                    "XDG_RUNTIME_DIR",
                    "DBUS_SESSION_BUS_ADDRESS",
                }
            },
        }
        if unit is None:
            unit = f"{unit_prefix}-{uuid.uuid4().hex}.scope"
        allowed_unit_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.@:-"
        )
        if not unit.endswith(".scope") or any(
            char not in allowed_unit_chars for char in unit
        ):
            raise ValueError("invalid Linux MXC systemd scope unit name")
        args = systemd_scope_command(systemd_run, unit, command)
        try:
            process = subprocess.Popen(
                args,
                cwd=str(cwd),
                env=safe_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                bufsize=0,
            )
        except OSError as exc:
            raise RuntimeError(
                f"could not start Linux MXC systemd scope: {exc}"
            ) from exc
        scope = cls(process, unit=unit, environment=bus_env, systemctl=systemctl)
        try:
            scope._wait_for_active_scope()
            scope._verify_resource_properties()
            scope._monitor.start()
        except Exception as startup_error:
            try:
                scope.stop()
            except Exception as stop_error:
                try:
                    scope._kill_scope_processes()
                    process.wait(timeout=STOP_TIMEOUT_SECONDS)
                    scope._verify_stopped()
                    scope._closed = True
                except Exception as cleanup_error:
                    # Keep a strong reference to the cgroup scope so the caller
                    # can also retain its workspace lease. Never report cleanup
                    # success merely because the systemd-run client was killed.
                    _UNREAPED_SCOPES.append(scope)
                    raise LinuxScopeCleanupError(
                        "Linux MXC startup failed and scope cleanup could not be verified: "
                        f"{cleanup_error}",
                        scope,
                    ) from startup_error
                raise RuntimeError(
                    f"Linux MXC startup failed; scope required forced cleanup: {stop_error}"
                ) from startup_error
            raise
        return scope

    @property
    def cpu_exceeded(self) -> bool:
        return self._cpu_exceeded

    @property
    def watchdog_error(self) -> str | None:
        return self._watchdog_error

    def _show(self, property_name: str) -> str:
        result = subprocess.run(
            [
                self.systemctl,
                "--user",
                "show",
                "--value",
                f"--property={property_name}",
                self.unit,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            env=self.environment,
            shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"could not verify Linux MXC cgroup property {property_name}: "
                f"{result.stderr.strip()[-500:]}"
            )
        return result.stdout.strip()

    def _wait_for_active_scope(self) -> None:
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stderr = b""
                if self.process.stderr:
                    try:
                        stderr = self.process.stderr.read(4096)
                    except OSError:
                        pass
                raise RuntimeError(
                    "Linux MXC systemd scope exited before activation: "
                    + stderr.decode("utf-8", errors="replace")[-1000:]
                )
            try:
                state = self._show("ActiveState")
                cgroup = self._show("ControlGroup")
                if state == "active" and cgroup:
                    self._cgroup_path = self._validate_cgroup_path(cgroup)
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(0.1)
        raise RuntimeError(
            "Linux MXC systemd scope did not become active with a cgroup"
            + (f": {last_error}" if last_error else "")
        )

    def _validate_cgroup_path(self, cgroup: str) -> Path:
        relative = Path(cgroup.lstrip("/"))
        root = CGROUP_ROOT.resolve(strict=True)
        resolved = (root / relative).resolve(strict=True)
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            raise RuntimeError("systemd returned a cgroup outside /sys/fs/cgroup")
        if not (resolved / "cgroup.procs").is_file():
            raise RuntimeError(
                "Linux MXC scope has no verifiable cgroup v2 process list"
            )
        return resolved

    def _verify_resource_properties(self) -> None:
        memory = _parse_bytes(self._show("MemoryMax"))
        swap = _parse_bytes(self._show("MemorySwapMax"))
        tasks = _parse_bytes(self._show("TasksMax"))
        cpu_accounting = self._show("CPUAccounting").lower()
        cpu_quota = _parse_systemd_duration_us(self._show("CPUQuotaPerSecUSec"))
        if memory is None or memory > MEMORY_LIMIT_BYTES:
            raise RuntimeError("Linux MXC scope did not enforce the 1 GiB memory limit")
        if swap != 0:
            raise RuntimeError("Linux MXC scope did not disable swap")
        if tasks is None or tasks > TASK_LIMIT:
            raise RuntimeError("Linux MXC scope did not enforce the 64-task limit")
        if cpu_accounting != "yes":
            raise RuntimeError("Linux MXC scope did not enable CPU accounting")
        if cpu_quota is None or cpu_quota > 1_000_000:
            raise RuntimeError("Linux MXC scope did not enforce the single-CPU quota")

    def _monitor_cpu(self) -> None:
        while not self._monitor_stop.wait(CPU_POLL_INTERVAL_SECONDS):
            if self.process.poll() is not None:
                return
            try:
                usage = int(self._show("CPUUsageNSec"))
            except (ValueError, RuntimeError) as exc:
                self._watchdog_error = str(exc)
                try:
                    self.stop()
                except Exception as stop_error:
                    self._watchdog_error = f"{exc}; stop failed: {stop_error}"
                return
            if usage >= CPU_BUDGET_NS:
                self._cpu_exceeded = True
                try:
                    self.stop()
                except Exception as exc:
                    self._watchdog_error = str(exc)
                return

    def _verify_stopped(self) -> None:
        state: str | None
        try:
            state = self._show("ActiveState")
        except RuntimeError:
            if self.process.poll() is None:
                raise
            state = None
        if state in {"active", "activating", "reloading", "deactivating"}:
            raise RuntimeError(f"Linux MXC cgroup remains active after stop ({state})")

        path = self._cgroup_path
        try:
            cgroup = self._show("ControlGroup")
        except RuntimeError:
            if self.process.poll() is None:
                raise
            cgroup = ""
        if cgroup:
            path = self._validate_cgroup_path(cgroup)
        if path is None:
            if state is None:
                raise RuntimeError("Linux MXC stopped without a verifiable cgroup path")
            return
        self._verify_cgroup_empty(path)

    @staticmethod
    def _verify_cgroup_empty(path: Path) -> None:
        root = CGROUP_ROOT.resolve(strict=True)
        resolved = path.resolve(strict=False)
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            raise RuntimeError("Linux MXC cgroup path is outside /sys/fs/cgroup")
        if not resolved.exists():
            return
        events = resolved / "cgroup.events"
        if not events.is_file():
            raise RuntimeError("cannot verify that Linux MXC cgroup is empty")
        populated = next(
            (
                line.split()[1]
                for line in events.read_text(encoding="ascii").splitlines()
                if line.startswith("populated ")
            ),
            None,
        )
        if populated != "0":
            raise RuntimeError("Linux MXC scope cgroup still contains processes")

    def _kill_scope_processes(self) -> None:
        result = subprocess.run(
            [
                self.systemctl,
                "--user",
                "kill",
                "--kill-whom=all",
                "--signal=SIGKILL",
                self.unit,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            env=self.environment,
            shell=False,
        )
        if result.returncode != 0 and self.process.poll() is None:
            raise RuntimeError(
                "could not kill Linux MXC scope processes: "
                + result.stderr.strip()[-500:]
            )

    def stop(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._monitor_stop.set()
            try:
                result = subprocess.run(
                    [self.systemctl, "--user", "stop", self.unit],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=STOP_TIMEOUT_SECONDS,
                    env=self.environment,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                # Do not wait for an untrusted process to handle SIGTERM. Kill
                # every task in this exact transient scope and verify cgroup
                # emptiness before releasing its workspace lease.
                self._kill_scope_processes()
                result = subprocess.run(
                    [self.systemctl, "--user", "stop", self.unit],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=STOP_TIMEOUT_SECONDS,
                    env=self.environment,
                    shell=False,
                )
            if result.returncode != 0:
                self._kill_scope_processes()
                result = subprocess.run(
                    [self.systemctl, "--user", "stop", self.unit],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=STOP_TIMEOUT_SECONDS,
                    env=self.environment,
                    shell=False,
                )
                if result.returncode != 0 and self.process.poll() is None:
                    raise RuntimeError(
                        "could not stop Linux MXC scope: "
                        + result.stderr.strip()[-500:]
                    )
            try:
                self.process.wait(timeout=STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                self._kill_scope_processes()
                try:
                    self.process.wait(timeout=STOP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired as remaining:
                    raise RuntimeError(
                        "Linux MXC systemd scope client did not exit after SIGKILL"
                    ) from remaining
            self._verify_stopped()
            self._closed = True

    def close(self) -> None:
        self.stop()
        if threading.current_thread() is not self._monitor:
            self._monitor.join(timeout=2)


def sys_platform_linux() -> bool:
    return os.name == "posix" and Path("/proc").is_dir()


def stop_stale_scope(scope_key: str) -> None:
    """Stop a worker left behind after its owning process lost the workspace lease."""
    if len(scope_key) != 64 or any(
        char not in "0123456789abcdef" for char in scope_key
    ):
        raise ValueError("invalid stale MXC scope key")
    if not sys_platform_linux():
        return
    environment = _user_bus_environment()
    systemctl = _system_binary("systemctl")
    unit = f"uagent-mxc-{scope_key}.scope"

    def show(property_name: str) -> str | None:
        result = subprocess.run(
            [
                systemctl,
                "--user",
                "show",
                "--value",
                f"--property={property_name}",
                unit,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            env=environment,
            shell=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).lower()
            if "not loaded" in detail or "not found" in detail:
                return None
            raise RuntimeError(
                f"cannot inspect stale MXC systemd scope {unit}: {detail[-300:]}"
            )
        return result.stdout.strip()

    state = show("ActiveState")
    if state is None:
        return
    if state in {"active", "activating", "reloading", "deactivating"}:
        stopped = subprocess.run(
            [systemctl, "--user", "stop", unit],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STOP_TIMEOUT_SECONDS,
            env=environment,
            shell=False,
        )
        if stopped.returncode != 0:
            raise RuntimeError(
                f"could not stop orphaned MXC scope {unit}: {stopped.stderr[-300:]}"
            )
        deadline = time.monotonic() + STOP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            state = show("ActiveState")
            if state is None or state not in {
                "active",
                "activating",
                "reloading",
                "deactivating",
            }:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"orphaned MXC scope remained active: {unit}")
    cgroup = show("ControlGroup")
    if not cgroup:
        return
    root = CGROUP_ROOT.resolve(strict=True)
    cgroup_path = (root / cgroup.lstrip("/")).resolve(strict=False)
    if os.path.commonpath((str(root), str(cgroup_path))) != str(root):
        raise RuntimeError("orphaned MXC scope points outside the cgroup v2 root")
    if not cgroup_path.exists():
        return
    events = cgroup_path / "cgroup.events"
    if not events.is_file():
        raise RuntimeError("cannot verify that an orphaned MXC cgroup is empty")
    populated = next(
        (
            line.split()[1]
            for line in events.read_text(encoding="ascii").splitlines()
            if line.startswith("populated ")
        ),
        None,
    )
    if populated != "0":
        raise RuntimeError("orphaned MXC cgroup still contains processes")


def verify_linux_host_support() -> dict[str, Any]:
    """Exercise a short real cgroup-v2 scope before Linux MXC is advertised."""
    scope = LinuxSystemdScope.launch(
        ["/usr/bin/sleep", "2"],
        cwd=Path("/"),
        env={},
        unit_prefix="uagent-mxc-probe",
    )
    try:
        result = scope.process.wait(timeout=5)
        if result != 0:
            raise RuntimeError("Linux MXC systemd scope probe returned non-zero")
        scope._verify_stopped()
        return {
            "ok": True,
            "backend": "systemd-cgroup-v2",
            "memory_limit_bytes": MEMORY_LIMIT_BYTES,
            "task_limit": TASK_LIMIT,
            "cpu_budget_ns": CPU_BUDGET_NS,
            "cpu_accounting": "watchdog at 500ms intervals with one CPU quota",
        }
    finally:
        scope.close()


__all__ = [
    "CPU_BUDGET_NS",
    "LinuxSystemdScope",
    "MEMORY_LIMIT_BYTES",
    "TASK_LIMIT",
    "systemd_scope_command",
    "stop_stale_scope",
    "verify_linux_host_support",
]

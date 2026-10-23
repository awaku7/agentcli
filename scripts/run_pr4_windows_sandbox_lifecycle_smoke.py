"""Run one real owner-bound MXC Windows Sandbox lifecycle smoke on Windows.

This is a manual acceptance helper, not a PR4 pass. Run from an elevated
PowerShell on the dedicated Windows Pro/Enterprise/Education test host. It
performs provision -> start -> guest exec -> stop -> deprovision and preserves
the temporary workspace if ownership-bound cleanup cannot be confirmed.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from uagent.runtime.windows_sandbox_lifecycle import (
    PINNED_MXC_VERSION,
    WindowsSandboxLease,
    WindowsSandboxLifecycleClient,
    WxcCommandResult,
    _default_command_runner,
)

MIN_FREE_MEMORY_MB = 2048
GUEST_MARKER = "UAG_PR4_LIFECYCLE_EXEC_OK"
HOST_BLOCKED_MARKER = "UAG_PR4_LIFECYCLE_HOST_PATH_BLOCKED"
HOST_VISIBLE_MARKER = "UAG_PR4_LIFECYCLE_HOST_PATH_VISIBLE"


def _require_windows_acceptance_host() -> dict[str, Any]:
    if os.name != "nt" or sys.maxsize <= 2**32:
        raise RuntimeError("lifecycle VM smoke requires Windows x64")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("run this script from an elevated PowerShell")

    import winreg

    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
    ) as key:
        edition = winreg.QueryValueEx(key, "EditionID")[0]
        build = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
    if edition not in {"Professional", "Enterprise", "Education"}:
        raise RuntimeError(f"unsupported Windows edition: {edition}")

    active = _active_windows_sandbox_processes()
    if active:
        raise RuntimeError(
            "refusing to overlap an active Windows Sandbox host process: "
            + ", ".join(active)
        )
    daemons = _active_lifecycle_daemons()
    if daemons:
        raise RuntimeError(
            "refusing to overlap an active MXC Windows Sandbox daemon: "
            + ", ".join(daemons)
        )
    vmmem_wait_seconds, vmmem_before_start = _wait_for_stale_vmmem()

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    memory = _MemoryStatus()
    memory.dwLength = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise RuntimeError("could not read host memory status")
    free_mb = memory.ullAvailPhys // (1024 * 1024)
    if free_mb < MIN_FREE_MEMORY_MB:
        raise RuntimeError(
            f"need at least {MIN_FREE_MEMORY_MB} MB free memory; found {free_mb} MB"
        )

    dism = subprocess.run(
        [
            "dism.exe",
            "/English",
            "/Online",
            "/Get-FeatureInfo",
            "/FeatureName:Containers-DisposableClientVM",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if dism.returncode != 0 or "State : Enabled" not in dism.stdout:
        raise RuntimeError("Windows Sandbox feature is not confirmed enabled")

    return {
        "edition": edition,
        "build": str(build),
        "free_memory_mb": int(free_mb),
        "vmmem_wait_seconds": round(vmmem_wait_seconds, 1),
        "vmmem_processes_before_start": vmmem_before_start,
        "sdk_version": PINNED_MXC_VERSION,
    }


def _active_windows_sandbox_processes() -> list[str]:
    check = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-Process -Name 'WindowsSandbox*' -ErrorAction SilentlyContinue | "
            "ForEach-Object { '{0}:{1}' -f $_.ProcessName, $_.Id }",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    if check.returncode != 0:
        raise RuntimeError("could not verify Windows Sandbox host processes")
    return [line.strip() for line in check.stdout.splitlines() if line.strip()]


def _active_lifecycle_daemons() -> list[str]:
    check = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-Process -Name 'wxc-windows-sandbox-daemon*' "
            "-ErrorAction SilentlyContinue | "
            "ForEach-Object { '{0}:{1}' -f $_.ProcessName, $_.Id }",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    if check.returncode != 0:
        raise RuntimeError("could not verify MXC Windows Sandbox daemon process")
    return [line.strip() for line in check.stdout.splitlines() if line.strip()]


def _vmmem_processes() -> list[str]:
    check = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-Process -Name 'vmmem*' -ErrorAction SilentlyContinue | "
            "ForEach-Object { '{0}:{1}' -f $_.ProcessName, $_.Id }",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    if check.returncode != 0:
        raise RuntimeError("could not inspect residual Hyper-V utility VM processes")
    return [line.strip() for line in check.stdout.splitlines() if line.strip()]


def _wait_for_stale_vmmem(
    *, timeout_seconds: int = 120, poll_seconds: int = 5
) -> tuple[float, list[str]]:
    """Wait briefly for prior WSB memory residue; never terminate vmmem processes."""
    started = time.monotonic()
    deadline = started + timeout_seconds
    while True:
        processes = _vmmem_processes()
        residual = [
            item
            for item in processes
            if item.partition(":")[0].lower() != "vmmemcmzygote"
        ]
        if not residual:
            return time.monotonic() - started, processes
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                "prior Hyper-V utility VM memory process remains; refusing a new start: "
                + ", ".join(residual)
            )
        time.sleep(min(poll_seconds, remaining))


def _recording_command_runner(records: list[dict[str, Any]]):
    """Capture bounded executor output for this fixed, credential-free smoke."""

    def run(argv: Sequence[str], timeout_seconds: float) -> WxcCommandResult:
        operation = "unknown"
        if "--operation" in argv:
            index = argv.index("--operation")
            if index + 1 < len(argv):
                operation = str(argv[index + 1])
        try:
            result = _default_command_runner(argv, timeout_seconds)
        except Exception as exc:
            records.append(
                {
                    "operation": operation,
                    "runner_error": f"{type(exc).__name__}: {str(exc)[:1000]}",
                }
            )
            raise
        records.append(
            {
                "operation": operation,
                "exit_code": result.returncode,
                "stdout": result.stdout[-8192:],
                "stderr": result.stderr[-8192:],
            }
        )
        return result

    return run


def _daemon_error_log_before_cleanup(sandbox_id: str) -> str | None:
    """Read the owner-specific daemon log before deprovision removes its state."""
    match = re.fullmatch(r"wsb:([0-9a-f]{8})", sandbox_id)
    if not match:
        return "sandbox ID is not in the expected owner-bound form"
    path = (
        Path(tempfile.gettempdir())
        / "wxc-wsb"
        / "state-aware"
        / match.group(1)
        / "daemon.log"
    )
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"daemon log could not be read: {type(exc).__name__}"
    text = re.sub(
        r"(?i)\b(nonce|token|secret|password)\b(\s*[=:]\s*)[^\s,;]+",
        r"\1\2[REDACTED]",
        text,
    )
    text = re.sub(r"\b[0-9a-fA-F]{32,}\b", "[REDACTED]", text)
    return chr(10).join(text.splitlines()[-100:])[-16_000:]


def _guest_command(host_canary: Path) -> str:
    canary = str(host_canary).replace("'", "''")
    script = (
        f"Write-Output {GUEST_MARKER}; "
        f"$p='{canary}'; "
        f"if (Test-Path -LiteralPath $p) "
        f"{{ Write-Output {HOST_VISIBLE_MARKER}; exit 9 }} "
        f"else {{ Write-Output {HOST_BLOCKED_MARKER}; exit 0 }}"
    )
    return "powershell.exe -NoLogo -NoProfile -NonInteractive " f'-Command "{script}"'


def run() -> int:
    host = _require_windows_acceptance_host()
    runtime_dir = Path(
        os.environ.get(
            "UAG_PR4_MXC_RUNTIME_DIR",
            str(Path(os.environ["LOCALAPPDATA"]) / "uagent" / "mxc_runtime"),
        )
    )
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex}"
    diagnostics_dir = Path(os.environ["LOCALAPPDATA"]) / "uagent" / "pr4_acceptance"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_path = diagnostics_dir / f"lifecycle-{run_id}.json"
    executor_calls: list[dict[str, Any]] = []
    client = WindowsSandboxLifecycleClient(
        runtime_dir,
        command_runner=_recording_command_runner(executor_calls),
        command_timeout_seconds=600,
    )
    work_root = Path(tempfile.mkdtemp(prefix=f"uag-pr4-lifecycle-{run_id}-"))
    workspace = work_root / "scope-workspace"
    host_canary = work_root / "host-only-canary.txt"
    report: dict[str, Any] = {
        "run_id": run_id,
        "host": host,
        "operations": [],
        "executor_calls": executor_calls,
        "workspace": str(work_root),
        "diagnostics": str(diagnostics_path),
    }
    lease: WindowsSandboxLease | None = None
    provision_attempted = False
    cleanup_confirmed = False
    failure: str | None = None

    try:
        workspace.mkdir()
        host_canary.write_text("UAG_PR4_HOST_CANARY", encoding="utf-8")
        provision_attempted = True
        lease = client.provision(workspace)
        report["sandbox_id"] = lease.sandbox_id
        report["operations"].append("provision:ok")

        client.start(lease)
        report["operations"].append("start:ok")

        result = client.execute(
            lease,
            command_line=_guest_command(host_canary),
            timeout_ms=30_000,
        )
        report["guest_exit_code"] = result.returncode
        report["guest_stdout"] = result.stdout[-8192:]
        report["guest_stderr"] = result.stderr[-8192:]
        if (
            result.returncode != 0
            or GUEST_MARKER not in result.stdout
            or HOST_BLOCKED_MARKER not in result.stdout
            or HOST_VISIBLE_MARKER in result.stdout
            or "UAG_PR4_HOST_CANARY" in result.stdout
        ):
            raise RuntimeError("guest lifecycle smoke or host-canary denial failed")
        report["operations"].append("exec:ok")

        client.stop(lease)
        report["operations"].append("stop:ok")
        client.deprovision(lease)
        report["operations"].append("deprovision:ok")
        cleanup_confirmed = lease.state == "closed"
        if not cleanup_confirmed:
            raise RuntimeError("MXC deprovision did not close the owned lease")
    except Exception as exc:  # retain diagnostics and perform owner-bound cleanup
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        safe_to_remove_workspace = lease is None and not provision_attempted
        if lease is not None and lease.state != "closed":
            daemon_log = _daemon_error_log_before_cleanup(lease.sandbox_id)
            if daemon_log:
                report["daemon_log_tail_before_cleanup"] = daemon_log
        if lease is not None:
            if lease.state == "closed":
                safe_to_remove_workspace = True
                cleanup_confirmed = True
            else:
                try:
                    client.terminate(lease)
                    safe_to_remove_workspace = lease.state == "closed"
                    cleanup_confirmed = safe_to_remove_workspace
                    report["operations"].append("owner_bound_cleanup:ok")
                except Exception as exc:
                    report["cleanup_error"] = f"{type(exc).__name__}: {exc}"
        elif provision_attempted:
            # A provision command with no trustworthy returned ID cannot be
            # reclaimed safely. Preserve its workspace and fail closed.
            report["cleanup_error"] = "provision outcome has no trustworthy owner ID"

        try:
            active = _active_windows_sandbox_processes()
        except Exception as exc:
            active = [f"process check failed: {type(exc).__name__}: {exc}"]
        report["active_windows_sandbox_processes_after_cleanup"] = active
        safe_to_remove_workspace = safe_to_remove_workspace and not active
        cleanup_confirmed = cleanup_confirmed and not active
        if safe_to_remove_workspace:
            try:
                import shutil

                shutil.rmtree(work_root)
                report["workspace_removed"] = True
            except OSError as exc:
                report["workspace_removed"] = False
                report["cleanup_error"] = f"workspace cleanup: {exc}"
                cleanup_confirmed = False
        else:
            report["workspace_removed"] = False
            report["workspace_preserved_for_safety"] = True

        if failure:
            report["failure"] = failure
        report["cleanup_confirmed"] = cleanup_confirmed and report["workspace_removed"]
        diagnostics_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failure and cleanup_confirmed else 1


if __name__ == "__main__":
    raise SystemExit(run())

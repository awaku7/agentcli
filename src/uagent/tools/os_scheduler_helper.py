from __future__ import annotations

import os
import platform
import subprocess
import sys
import types
import uuid
from datetime import datetime
from typing import Any

_JOB_PREFIX = "uag_timer_"


def detect_os() -> str:
    system = platform.system().lower()
    if system in ("windows", "darwin", "linux"):
        return system
    return "unknown"


def _sanitize_message(text: str) -> str:
    return text.replace('"', "'")


def _build_uag_command(
    workdir: str | None,
    message: str,
    on_timeout_prompt: str = "",
    tool_genre_mask: int = 0,
) -> str:
    python = sys.executable
    cmd = f'"{python}" -m uagent'
    payload = on_timeout_prompt or message
    safe_msg = _sanitize_message(payload)
    cmd += f' --inject-message "{safe_msg}"'
    if workdir:
        cmd += f' --workdir "{workdir}"'
    if tool_genre_mask > 0:
        cmd += f" --tool-genre-mask {tool_genre_mask}"
    return cmd


def _generate_job_name() -> str:
    return _JOB_PREFIX + str(uuid.uuid4())


def create_os_schedule(
    at_dt: datetime,
    message: str,
    on_timeout_prompt: str = "",
    workdir: str | None = None,
    job_name: str | None = None,
    tool_genre_mask: int = 0,
) -> dict[str, Any]:
    """Create an OS-level scheduled task.

    Returns dict with keys: ok, job_name, message, raw_output
    """
    os_type = detect_os()
    name = job_name or _generate_job_name()
    uag_cmd = _build_uag_command(workdir, message, on_timeout_prompt, tool_genre_mask=tool_genre_mask)

    # Convert to local time for OS scheduler (schtasks / at use local TZ)
    local_dt = at_dt.astimezone()

    if os_type == "windows":
        return _create_windows_schedule(name, uag_cmd, local_dt, workdir=workdir)
    elif os_type in ("darwin", "linux"):
        return _create_unix_schedule(name, uag_cmd, local_dt)
    else:
        return {"ok": False, "job_name": name, "message": f"Unsupported OS: {os_type}"}


def delete_os_schedule(job_name: str) -> dict[str, Any]:
    """Delete an OS-level scheduled task."""
    os_type = detect_os()
    if os_type == "windows":
        return _delete_windows_schedule(job_name)
    elif os_type in ("darwin", "linux"):
        return _delete_unix_schedule(job_name)
    else:
        return {"ok": False, "job_name": job_name, "message": f"Unsupported OS: {os_type}"}


def list_os_schedules() -> list[dict[str, Any]]:
    """List all OS-level scheduled tasks created by uag."""
    os_type = detect_os()
    if os_type == "windows":
        return _list_windows_schedules()
    elif os_type in ("darwin", "linux"):
        return _list_unix_schedules()
    return []


# =====================================================================
# Windows (schtasks)
# =====================================================================


def _run_schtasks(args: str) -> types.SimpleNamespace:
    full = f"schtasks {args}"
    result = subprocess.run(
        full, capture_output=True, text=False, shell=True, timeout=30
    )
    stdout = _decode_schtasks_output(result.stdout)
    stderr = _decode_schtasks_output(result.stderr)
    return types.SimpleNamespace(
        returncode=result.returncode, stdout=stdout, stderr=stderr
    )


def _decode_schtasks_output(data: bytes) -> str:
    for encoding in ["utf-8", "cp932", "shift_jis", "latin-1"]:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _create_windows_schedule(name: str, cmd: str, at_dt: datetime, workdir: str | None = None) -> dict[str, Any]:
    time_str = at_dt.strftime("%H:%M")
    date_str = at_dt.strftime("%Y/%m/%d")

    # Write a batch file that: runs uag, pauses for user to see output, then self-deletes
    bat_dir = os.path.join(os.path.expanduser("~"), ".uag", "scheduled")
    os.makedirs(bat_dir, exist_ok=True)
    bat_path = os.path.join(bat_dir, f"{name}.bat")
    wd_display = workdir or "(default)"
    log_path = os.path.join(bat_dir, f"{name}.log")
    bat_lines = [
        "@echo off",
        f"echo [uag] Timer firing: {name}",
        f"echo [uag] Workdir: {wd_display}",
        f"echo [uag] Log: {log_path}",
        f"{cmd} > \"{log_path}\" 2>&1",
        f"type \"{log_path}\"",
        "echo.",
        "echo [uag] Timer finished. Press any key to close...",
        "pause > nul",
        f"schtasks /delete /tn \"{name}\" /f > nul 2>&1",
        f"del /f \"{bat_path}\" > nul 2>&1",
        f"del /f \"{log_path}\" > nul 2>&1",
    ]
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("\n".join(bat_lines) + "\n")

    result = _run_schtasks(
        f'/create /tn "{name}" /tr "{bat_path}" /sc once /st "{time_str}" /sd "{date_str}" /f'
    )
    return {
        "ok": result.returncode == 0,
        "job_name": name,
        "raw_output": (result.stdout + result.stderr).strip(),
        "message": result.stdout.strip() or result.stderr.strip() or "OK",
    }


def _delete_windows_schedule(name: str) -> dict[str, Any]:
    result = _run_schtasks(f'/delete /tn "{name}" /f')
    return {
        "ok": result.returncode == 0,
        "job_name": name,
        "raw_output": (result.stdout + result.stderr).strip(),
        "message": result.stdout.strip() or result.stderr.strip() or "Deleted",
    }


def _list_windows_schedules() -> list[dict[str, Any]]:
    result = _run_schtasks("/query /fo csv /v")
    if result.returncode != 0:
        return []
    jobs: list[dict[str, Any]] = []
    for line in result.stdout.strip().split("\n"):
        if _JOB_PREFIX in line:
            parts = [p.strip('"') for p in line.split(',"')]
            job_name = parts[0] if parts else ""
            jobs.append({"job_name": job_name, "raw": line})
    return jobs


# =====================================================================
# Linux: systemd-run (primary) / at (fallback)
# =====================================================================


def _has_systemd() -> bool:
    try:
        r = subprocess.run(
            ["systemd-run", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _calc_delta_seconds(at_dt: datetime) -> int:
    now = datetime.now().astimezone()
    return max(1, int((at_dt - now).total_seconds()))


def _try_systemd_run(name: str, cmd: str, at_dt: datetime) -> dict[str, Any]:
    if not _has_systemd():
        return {"ok": False, "job_name": name, "message": "systemd not available"}
    delta = _calc_delta_seconds(at_dt)
    try:
        proc = subprocess.run(
            [
                "systemd-run", "--user",
                "--unit", name,
                "--on-active", str(delta),
                "--same-dir",
                "--collect",
                "--", "sh", "-c", cmd,
            ],
            capture_output=True, text=True, timeout=30,
        )
        out = (proc.stdout + proc.stderr).strip()
        return {
            "ok": proc.returncode == 0,
            "job_name": name,
            "raw_output": out,
            "message": out or "OK",
        }
    except FileNotFoundError:
        return {"ok": False, "job_name": name, "message": "systemd-run not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "job_name": name, "message": "systemd-run timed out"}
    except Exception as e:
        return {"ok": False, "job_name": name, "message": str(e)}


def _delete_systemd_unit(name: str) -> dict[str, Any]:
    try:
        subprocess.run(
            ["systemctl", "--user", "stop", name],
            capture_output=True, timeout=15,
        )
        subprocess.run(
            ["systemctl", "--user", "reset-failed", name],
            capture_output=True, timeout=15,
        )
        return {"ok": True, "job_name": name, "message": f"Systemd unit {name} stopped"}
    except Exception as e:
        return {"ok": False, "job_name": name, "message": str(e)}


def _list_systemd_units() -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "list-timers", "--all", "--no-legend"],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            return []
        jobs: list[dict[str, Any]] = []
        for line in proc.stdout.strip().split("\n"):
            if _JOB_PREFIX in line:
                parts = line.split()
                unit = parts[-1] if parts else ""
                jobs.append({"job_name": unit, "raw": line})
        return jobs
    except Exception:
        return []


# =====================================================================
# Unix fallback: at command (Linux / macOS)
# =====================================================================


def _is_at_available() -> bool:
    try:
        r = subprocess.run(["at", "-V"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _run_at(cmd: str, at_dt: datetime) -> dict[str, Any]:
    time_str = at_dt.strftime("%H:%M")
    date_str = at_dt.strftime("%Y-%m-%d")
    try:
        proc = subprocess.run(
            ["at", f"{time_str} {date_str}"],
            input=cmd + "\n",
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {
            "ok": proc.returncode == 0,
            "raw_output": (proc.stdout + proc.stderr).strip(),
            "message": proc.stdout.strip() or proc.stderr.strip() or "OK",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "raw_output": "",
            "message": (
                "'at' command not found. "
                "On Linux: apt install at. "
                "On macOS: enable atrun with 'sudo launchctl load -w "
                "/System/Library/LaunchDaemons/com.apple.atrun.plist'."
            ),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "raw_output": "", "message": "at command timed out"}
    except Exception as e:
        return {"ok": False, "raw_output": "", "message": str(e)}


def _create_unix_schedule(name: str, cmd: str, at_dt: datetime) -> dict[str, Any]:
    # Linux: try systemd-run first
    if detect_os() == "linux":
        result = _try_systemd_run(name, cmd, at_dt)
        if result.get("ok"):
            return result
        # Fall through to at if systemd failed AND at is available
        if not _is_at_available():
            return result
    # Fallback: at command
    tagged_cmd = f"# {name}\n{cmd}"
    result = _run_at(tagged_cmd, at_dt)
    result["job_name"] = name
    return result


def _delete_unix_schedule(name: str) -> dict[str, Any]:
    # Try systemd first on Linux
    if detect_os() == "linux" and _has_systemd():
        result = _delete_systemd_unit(name)
        # Check if it was actually a systemd unit
        if _list_systemd_units():
            return result
    # Fallback: at queue
    try:
        atq = subprocess.run(
            ["atq"], capture_output=True, text=True, timeout=15
        )
        if atq.returncode != 0:
            return {"ok": False, "job_name": name, "message": "atq command failed"}
        for line in atq.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if not parts:
                continue
            job_id = parts[0]
            check = subprocess.run(
                ["at", "-c", job_id],
                capture_output=True, text=True, timeout=15,
            )
            if name in check.stdout:
                subprocess.run(
                    ["atrm", job_id], capture_output=True, timeout=15
                )
                return {"ok": True, "job_name": name, "message": f"Deleted at job {job_id}"}
        return {"ok": False, "job_name": name, "message": "Job not found"}
    except FileNotFoundError:
        return {"ok": False, "job_name": name, "message": "'at' command not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "job_name": name, "message": "Command timed out"}
    except Exception as e:
        return {"ok": False, "job_name": name, "message": str(e)}


def _list_unix_schedules() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    # Try systemd units on Linux
    if detect_os() == "linux" and _has_systemd():
        jobs = _list_systemd_units()
    # Also check at queue
    try:
        atq = subprocess.run(
            ["atq"], capture_output=True, text=True, timeout=15
        )
        if atq.returncode == 0:
            for line in atq.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if not parts:
                    continue
                job_id = parts[0]
                check = subprocess.run(
                    ["at", "-c", job_id],
                    capture_output=True, text=True, timeout=15,
                )
                if _JOB_PREFIX in check.stdout:
                    jobs.append({"job_name": job_id, "raw": line})
    except Exception:
        pass
    return jobs

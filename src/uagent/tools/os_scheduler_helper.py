from __future__ import annotations

import os
import platform
import re
import shlex
import subprocess
import sys
import types
import uuid
from datetime import datetime
from typing import Any

from ..scheduler.os_payload import (
    create_scheduled_payload,
    delete_scheduled_payload,
    scheduled_payload_directory,
)

from ..util_tools import strip_surrogates
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_JOB_PREFIX = "uag_timer_"
_JOB_NAME_RE = re.compile(r"^uag_timer_([0-9a-f]{32})$")


def detect_os() -> str:
    system = platform.system().lower()
    if system in ("windows", "darwin", "linux"):
        return system
    return _("os_sched.unknown", default="unknown")


def _build_uag_argv(payload_id: str, payload_dir: str) -> list[str]:
    """Build an argv containing no prompt, arguments, or credentials."""
    return [
        sys.executable,
        "-m",
        "uagent",
        "--scheduled-payload-id",
        payload_id,
        "--scheduled-payload-dir",
        payload_dir,
    ]


def _generate_job_name(payload_id: str | None = None) -> str:
    return _JOB_PREFIX + (payload_id or uuid.uuid4().hex)


def create_os_schedule(
    at_dt: datetime,
    message: str,
    on_timeout_prompt: str = "",
    workdir: str | None = None,
    job_name: str | None = None,
    tool_genre_mask: int = 0,
    enable_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Create an OS-level scheduled task.

    Returns dict with keys: ok, job_name, message, raw_output
    """
    os_type = detect_os()
    if job_name:
        match = _JOB_NAME_RE.fullmatch(str(job_name))
        if match is None:
            return {
                "ok": False,
                "job_name": str(job_name),
                "message": "Invalid OS scheduler job name",
            }
        payload_id = match.group(1)
    else:
        payload_id = uuid.uuid4().hex
    payload_id = create_scheduled_payload(
        {
            "message": message,
            "on_timeout_prompt": on_timeout_prompt,
            "workdir": os.path.abspath(workdir) if workdir else "",
            "enable_tools": list(enable_tools or []),
        },
        payload_id=payload_id,
    )
    payload_dir = scheduled_payload_directory().resolve(strict=True)
    name = _generate_job_name(payload_id)
    argv = _build_uag_argv(payload_id, str(payload_dir))

    # Convert to local time for OS scheduler (schtasks / at use local TZ).
    local_dt = at_dt.astimezone()
    try:
        if os_type == "windows":
            result = _create_windows_schedule(name, argv, local_dt)
        elif os_type in ("darwin", "linux"):
            result = _create_unix_schedule(name, argv, local_dt)
        else:
            result = {
                "ok": False,
                "job_name": name,
                "message": f"Unsupported OS: {os_type}",
            }
    except Exception as exc:
        delete_scheduled_payload(payload_id, payload_dir)
        return {"ok": False, "job_name": name, "message": str(exc)}
    if not result.get("ok"):
        delete_scheduled_payload(payload_id, payload_dir)
    result["payload_id"] = payload_id if result.get("ok") else ""
    return result


def delete_os_schedule(job_name: str) -> dict[str, Any]:
    """Delete an OS-level scheduled task and its unconsumed one-shot payload."""
    os_type = detect_os()
    if os_type == "windows":
        result = _delete_windows_schedule(job_name)
    elif os_type in ("darwin", "linux"):
        result = _delete_unix_schedule(job_name)
    else:
        return {
            "ok": False,
            "job_name": job_name,
            "message": f"Unsupported OS: {os_type}",
        }
    if result.get("ok") and str(job_name).startswith(_JOB_PREFIX):
        payload_id = str(job_name)[len(_JOB_PREFIX) :]
        try:
            delete_scheduled_payload(payload_id)
        except ValueError:
            pass
    return result


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


def _run_schtasks(args: list[str]) -> types.SimpleNamespace:
    result = subprocess.run(
        ["schtasks", *args], capture_output=True, text=False, shell=False, timeout=30
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


def _create_windows_schedule(
    name: str, argv: list[str], at_dt: datetime
) -> dict[str, Any]:
    time_str = at_dt.strftime("%H:%M")
    date_str = at_dt.strftime("%Y/%m/%d")
    # schtasks accepts one command string for /tr. list2cmdline applies Windows
    # argv quoting; argv contains only the interpreter, fixed module/flag names,
    # and a validated opaque payload ID (never the prompt or workdir).
    command = subprocess.list2cmdline(argv)
    result = _run_schtasks(
        [
            "/create",
            "/tn",
            name,
            "/tr",
            command,
            "/sc",
            "once",
            "/st",
            time_str,
            "/sd",
            date_str,
            "/f",
            "/Z",
        ]
    )
    return {
        "ok": result.returncode == 0,
        "job_name": name,
        "raw_output": (result.stdout + result.stderr).strip(),
        "message": result.stdout.strip() or result.stderr.strip() or "OK",
    }


def _delete_windows_schedule(name: str) -> dict[str, Any]:
    result = _run_schtasks(["/delete", "/tn", name, "/f"])
    return {
        "ok": result.returncode == 0,
        "job_name": name,
        "raw_output": (result.stdout + result.stderr).strip(),
        "message": result.stdout.strip() or result.stderr.strip() or "Deleted",
    }


def _list_windows_schedules() -> list[dict[str, Any]]:
    result = _run_schtasks(["/query", "/fo", "csv", "/v"])
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
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _calc_delta_seconds(at_dt: datetime) -> int:
    now = datetime.now().astimezone()
    return max(1, int((at_dt - now).total_seconds()))


def _try_systemd_run(name: str, argv: list[str], at_dt: datetime) -> dict[str, Any]:
    if not _has_systemd():
        return {"ok": False, "job_name": name, "message": "systemd not available"}
    delta = _calc_delta_seconds(at_dt)
    try:
        proc = subprocess.run(
            [
                "systemd-run",
                "--user",
                "--unit",
                name,
                "--on-active",
                str(delta),
                "--collect",
                "--",
                *argv,
            ],
            capture_output=True,
            text=True,
            timeout=30,
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
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["systemctl", "--user", "reset-failed", name],
            capture_output=True,
            timeout=15,
        )
        return {"ok": True, "job_name": name, "message": f"Systemd unit {name} stopped"}
    except Exception as e:
        return {"ok": False, "job_name": name, "message": str(e)}


def _list_systemd_units() -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "list-timers", "--all", "--no-legend"],
            capture_output=True,
            text=True,
            timeout=15,
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


def _run_at(name: str, argv: list[str], at_dt: datetime) -> dict[str, Any]:
    time_str = at_dt.strftime("%H:%M")
    date_str = at_dt.strftime("%Y-%m-%d")
    try:
        proc = subprocess.run(
            ["at", f"{time_str} {date_str}"],
            input=f"# {name}"
            + chr(10)
            + shlex.join(strip_surrogates(arg) for arg in argv)
            + chr(10),
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


def _create_unix_schedule(
    name: str, argv: list[str], at_dt: datetime
) -> dict[str, Any]:
    # Linux: launch argv directly through systemd, never via ``sh -c``.
    if detect_os() == "linux":
        result = _try_systemd_run(name, argv, at_dt)
        if result.get("ok"):
            return result
        if not _is_at_available():
            return result
    # at consumes a shell command; quote every argument using POSIX rules.
    result = _run_at(name, argv, at_dt)
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
        atq = subprocess.run(["atq"], capture_output=True, text=True, timeout=15)
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
                capture_output=True,
                text=True,
                timeout=15,
            )
            if name in check.stdout:
                subprocess.run(["atrm", job_id], capture_output=True, timeout=15)
                return {
                    "ok": True,
                    "job_name": name,
                    "message": f"Deleted at job {job_id}",
                }
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
        atq = subprocess.run(["atq"], capture_output=True, text=True, timeout=15)
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
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if _JOB_PREFIX in check.stdout:
                    jobs.append({"job_name": job_id, "raw": line})
    except Exception:
        pass
    return jobs

"""Best-effort private, per-process OTLP delivery status without network probes.

Only enums and timestamps are persisted; never endpoint URLs, credentials,
span attributes, exception text or conversation content. Status describes the
last *attempted export*, not current Admin reachability.
"""

from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Any

from ...utils.paths import get_state_dir

_STATES = frozenset(
    {
        "disabled",
        "dependencies_unavailable",
        "backend_unavailable",
        "backend_initialization_failed",
        "no_endpoint",
        "awaiting_export",
        "sent",
        "failed",
        "retry_cooldown",
    }
)
_LOCK = threading.RLock()
_PID = os.getpid()
_FILE: Path | None = None
_STATUS: dict[str, Any] | None = None
_CLEANUP_REGISTERED = False


def _identity() -> tuple[int, float]:
    import psutil

    process = psutil.Process(os.getpid())
    return os.getpid(), process.create_time()


def _path() -> Path:
    pid, started = _identity()
    return get_state_dir() / "otel_delivery" / f"{pid}-{int(started * 1000000)}.json"


def _private_dir(directory: Path) -> None:
    if directory.is_symlink():
        raise PermissionError("unsafe OTLP status directory")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise PermissionError("unsafe OTLP status directory")
    if os.name != "nt" and (
        directory.stat().st_mode & 0o077 or directory.stat().st_uid != os.getuid()
    ):
        raise PermissionError("OTLP status directory is not private")
    if os.name == "nt":
        from ..process_registry import _windows_protect

        _windows_protect(directory)


def _save(path: Path, data: dict[str, Any]) -> None:
    _private_dir(path.parent)
    if path.is_symlink():
        raise PermissionError("unsafe OTLP status target")
    tmp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=True, separators=(",", ":"))
            stream.write("\n")
        if os.name == "nt":
            from ..process_registry import _windows_protect

            _windows_protect(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _cleanup() -> None:
    global _FILE
    with _LOCK:
        path = _FILE
        _FILE = None
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def update_delivery_status(state: str, *, enabled: bool = True) -> None:
    """Record bounded state transitions. Never block or fail Agent execution."""
    global _PID, _FILE, _STATUS, _CLEANUP_REGISTERED
    if state not in _STATES:
        return
    try:
        with _LOCK:
            if _PID != os.getpid():
                # Avoid inheriting parent's file handle after fork.
                _PID = os.getpid()
                _FILE = None
                _STATUS = None
            path = _path()
            if _FILE is not None and _FILE != path:
                _cleanup()
                _STATUS = None
            pid, started = _identity()
            now = int(time.time())
            if _STATUS is None:
                _STATUS = {
                    "version": 1,
                    "pid": pid,
                    "create_time": started,
                    "enabled": False,
                    "state": "disabled",
                    "updated_at": now,
                    "last_attempt_at": None,
                    "last_success_at": None,
                    "last_failure_at": None,
                }
            if state == "disabled":
                _STATUS["last_attempt_at"] = None
                _STATUS["last_success_at"] = None
                _STATUS["last_failure_at"] = None
            _STATUS["enabled"] = bool(enabled)
            _STATUS["state"] = state
            _STATUS["updated_at"] = now
            if state in {"sent", "failed"}:
                _STATUS["last_attempt_at"] = now
                _STATUS[
                    "last_success_at" if state == "sent" else "last_failure_at"
                ] = now
            _save(path, _STATUS)
            _FILE = path
            if not _CLEANUP_REGISTERED:
                atexit.register(_cleanup)
                _CLEANUP_REGISTERED = True
    except Exception:
        # Optional status file errors must not affect telemetry or Agent work.
        pass


def local_delivery_statuses() -> list[dict[str, Any]]:
    """Read only live same-user UAG senders; never trust a stale PID alone."""
    import psutil

    directory = get_state_dir() / "otel_delivery"
    try:
        if directory.is_symlink() or not directory.is_dir():
            return []
        if os.name != "nt" and (
            directory.stat().st_mode & 0o077 or directory.stat().st_uid != os.getuid()
        ):
            return []
        paths = sorted(directory.glob("*.json"))
        if len(paths) > 256:
            return []
    except OSError:
        return []
    result = []
    keys = frozenset(
        {
            "version",
            "pid",
            "create_time",
            "enabled",
            "state",
            "updated_at",
            "last_attempt_at",
            "last_success_at",
            "last_failure_at",
        }
    )
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 2048:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if type(data) is not dict or frozenset(data) != keys:
                continue
            pid, started = data["pid"], data["create_time"]
            if (
                type(data["version"]) is not int
                or data["version"] != 1
                or type(pid) is not int
                or pid < 1
                or type(started) not in (int, float)
                or type(data["enabled"]) is not bool
                or data["state"] not in _STATES
                or any(
                    value is not None and (type(value) is not int or value < 0)
                    for value in (
                        data["updated_at"],
                        data["last_attempt_at"],
                        data["last_success_at"],
                        data["last_failure_at"],
                    )
                )
                or path.name != f"{pid}-{int(started * 1000000)}.json"
                or abs(psutil.Process(pid).create_time() - started) > 0.1
            ):
                continue
            result.append(data)
        except (OSError, ValueError, TypeError, KeyError, psutil.Error):
            continue
    return result

"""Structured logging for Matter tools.

Logs each tool execution as a JSON Line to a file or stderr.
Controlled by environment variables:

- UAGENT_MATTER_LOG_DIR: directory for log files (default: outputs/matter/)
- UAGENT_MATTER_LOG_LEVEL: debug/info/warn/error (default: info)
- UAGENT_MATTER_LOG_RETENTION_DAYS: days to keep logs (default: 30)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_LEVELS = {"debug": 0, "info": 1, "warn": 2, "error": 3}

# Cache for log dir to avoid repeated stat calls
_log_dir: str | None = None
_log_level: int = 1  # info default


def _get_log_dir() -> str:
    global _log_dir
    if _log_dir is None:
        _log_dir = os.getenv("UAGENT_MATTER_LOG_DIR", "").strip() or "outputs/matter"
    return _log_dir


def _get_log_level() -> int:
    global _log_level
    raw = os.getenv("UAGENT_MATTER_LOG_LEVEL", "info").strip().lower()
    return _LOG_LEVELS.get(raw, 1)


def _mask_sensitive(value: Any) -> Any:
    """Mask sensitive values in log output."""
    if isinstance(value, str):
        s = value.lower()
        if any(kw in s for kw in ("key", "token", "password", "secret", "credential")):
            return "***"
    return value


def _sanitize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive fields from args dict for logging."""
    return {k: _mask_sensitive(v) for k, v in args.items()}


def matter_log(
    tool_name: str,
    args: dict[str, Any],
    ok: bool,
    elapsed_ms: float,
    error: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    """Write a structured log entry for a Matter tool execution.

    The log entry is a JSON Line written to a daily log file.
    """
    if _LOG_LEVELS.get(level, 1) < _get_log_level():
        return

    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "tool": tool_name,
        "args": _sanitize_args(args),
        "ok": ok,
        "elapsed_ms": round(elapsed_ms, 1),
    }
    if error:
        entry["error"] = error

    log_dir = _get_log_dir()
    if not log_dir:
        return

    date_str = datetime.now().strftime("%Y%m%d")
    log_path = Path(log_dir) / f"matter_{date_str}.log"

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # Silently ignore write errors


class LogTimer:
    """Context manager that logs tool execution time.

    Usage:
        with LogTimer("matter_device_status", args) as timer:
            result = do_work()
        # timer.result is set automatically on success
        # On exception, timer logs with error level
    """

    def __init__(self, tool_name: str, args: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.args = args
        self._start: float | None = None

    def __enter__(self) -> LogTimer:
        self._start = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        elapsed = (time.time() - self._start) * 1000 if self._start else 0
        if exc_type is not None:
            matter_log(
                self.tool_name,
                self.args,
                ok=False,
                elapsed_ms=elapsed,
                error={"code": "exception", "message": str(exc_val)},
                level="error",
            )
        else:
            matter_log(
                self.tool_name,
                self.args,
                ok=True,
                elapsed_ms=elapsed,
                level="info",
            )

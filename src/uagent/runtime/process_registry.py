"""Best-effort, user-private local process registration for UAG Admin.

Records contain only the stable instance UUID and process identity. They do
not authorize requests, process termination, or privilege escalation.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
from typing import Iterator

import psutil

from .instance_identity import get_instance_id
from ..utils.paths import get_state_dir

_ENTRYPOINTS = frozenset({"cli", "gui", "web", "a2a"})


def _register(entrypoint: str) -> Path:
    if entrypoint not in _ENTRYPOINTS:
        raise ValueError("invalid UAG entrypoint")

    directory = get_state_dir() / "process_registry"
    if directory.is_symlink():
        raise PermissionError("unsafe process registry directory")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise PermissionError("unsafe process registry directory")
    if os.name != "nt" and directory.stat().st_mode & 0o077:
        raise PermissionError("process registry directory is not private")

    pid = os.getpid()
    start = psutil.Process(pid).create_time()
    identity = get_instance_id()
    payload = {
        "version": 1,
        "instance_id": identity,
        "entrypoint": entrypoint,
        "pid": pid,
        "create_time": start,
    }
    filename = f"{pid}-{int(start * 1_000_000)}-{entrypoint}.json"
    target = directory / filename
    pending = directory / f".{filename}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(str(pending), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=True, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)
    return target


@contextmanager
def tracked_process(entrypoint: str) -> Iterator[None]:
    """Register one running entrypoint without disrupting UAG if unavailable."""
    record = None
    try:
        record = _register(entrypoint)
    except (OSError, ValueError, PermissionError, psutil.Error):
        pass

    try:
        yield
    finally:
        if record is not None:
            try:
                # Remove only our own record; its PID + birth time is unique.
                record.unlink(missing_ok=True)
            except OSError:
                pass

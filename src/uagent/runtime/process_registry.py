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


_ACTIVE: dict[str, Path] = {}


def _windows_protect(path: Path) -> None:
    """Enforce an owner-only protected DACL before storing any process record."""
    if os.name != "nt":
        return
    import win32api
    import win32con
    import win32security

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
    )
    sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_ALL, sid)
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(sid, False)
    descriptor.SetSecurityDescriptorDacl(True, dacl, False)
    descriptor.SetSecurityDescriptorControl(
        win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED
    )
    win32security.SetFileSecurity(
        str(path),
        win32security.OWNER_SECURITY_INFORMATION
        | win32security.DACL_SECURITY_INFORMATION,
        descriptor,
    )

    actual = win32security.GetFileSecurity(
        str(path),
        win32security.OWNER_SECURITY_INFORMATION
        | win32security.DACL_SECURITY_INFORMATION,
    )
    control, _ = actual.GetSecurityDescriptorControl()
    actual_acl = actual.GetSecurityDescriptorDacl()
    if (
        actual.GetSecurityDescriptorOwner() != sid
        or not control & win32security.SE_DACL_PROTECTED
        or actual_acl is None
        or actual_acl.GetAceCount() != 1
    ):
        raise PermissionError("UAG process registry Windows ACL is not private")
    ace = actual_acl.GetAce(0)
    if (
        ace[0][0] != win32security.ACCESS_ALLOWED_ACE_TYPE
        or ace[0][1] != 0
        or ace[2] != sid
    ):
        raise PermissionError("UAG process registry DACL is not owner-only")


def clear_tracking(entrypoint: str) -> None:
    record = _ACTIVE.pop(entrypoint, None)
    if record is not None:
        try:
            record.unlink(missing_ok=True)
        except OSError:
            pass


def activate_tracking(entrypoint: str) -> None:
    """Best-effort registration only *after* workdir and dotenv resolution."""
    clear_tracking(entrypoint)
    try:
        _ACTIVE[entrypoint] = _register(entrypoint)
    except (
        OSError,
        ValueError,
        RuntimeError,
        PermissionError,
        psutil.Error,
        ImportError,
    ):
        pass


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
    _windows_protect(directory)

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
        _windows_protect(pending)
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
    except (
        OSError,
        ValueError,
        RuntimeError,
        PermissionError,
        psutil.Error,
        ImportError,
    ):
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

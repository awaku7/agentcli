"""Principal and session scoped, non-secret MXC environment settings.

Only the trusted host reads these files. Never accept identity or settings paths
from a sandbox tool request, project dotenv, or a model-supplied argument.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Any

from .execution_broker import TrustedSandboxScope

_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_RESERVED = frozenset(
    {
        "HOME",
        "PATH",
        "TMP",
        "TEMP",
        "TMPDIR",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "SYSTEMROOT",
        "WINDIR",
        "ENV",
        "BASH_ENV",
        "SHELLOPTS",
        "NODE_OPTIONS",
        "GIT_ASKPASS",
        "SSH_ASKPASS",
        "GIT_SSH",
        "GIT_SSH_COMMAND",
        "GIT_EXEC_PATH",
        "PIP_CONFIG_FILE",
        "PYTHONPATH",
        "PYTHONHOME",
    }
)
_RESERVED_PREFIXES = ("UAGENT_", "LD_", "DYLD_", "GIT_CONFIG_", "PYTHON")
_SECRET_PARTS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "PRIVATE_KEY",
    "ACCESS_KEY",
    "CREDENTIAL",
    "AUTH_SOCK",
)


def settings_path(root: Path, scope: TrustedSandboxScope, level: str) -> Path:
    """Return a pseudonymous filename keyed only by trusted scope identity."""
    if not isinstance(scope, TrustedSandboxScope):
        raise TypeError("a trusted sandbox scope is required")
    if level == "user":
        parts = (scope.deployment_id, scope.principal_id)
    elif level == "session":
        parts = (
            scope.deployment_id,
            scope.principal_id,
            scope.project_id,
            scope.scope_kind,
            scope.scope_id,
            scope.binding_generation,
        )
    else:
        raise ValueError("settings level must be user or session")
    identity = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return Path(root) / "uag" / "sandbox_settings" / level / (key + ".json")


def _validate_environment(environment: Any) -> dict[str, str]:
    if not isinstance(environment, dict) or len(environment) > 64:
        raise ValueError("sandbox environment must contain at most 64 variables")
    checked = {}
    for name, value in environment.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("invalid sandbox environment variable name")
        if (
            name in _RESERVED
            or name.startswith(_RESERVED_PREFIXES)
            or any(part in name for part in _SECRET_PARTS)
        ):
            raise ValueError("protected or credential environment variable")
        if not isinstance(value, str) or len(value) > 2048:
            raise ValueError("sandbox environment values must be bounded strings")
        if any(char in value for char in ("\0", "\r", "\n")):
            raise ValueError("sandbox environment values cannot contain controls")
        if name in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}:
            from urllib.parse import urlsplit

            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError("proxy URLs must not contain credentials")
        checked[name] = value
    return checked


def _check_directory(path: Path, *, require_private: bool = True) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(info.st_mode) or getattr(
        info, "st_file_attributes", 0
    ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise PermissionError("sandbox settings directory is not a real directory")
    if require_private and os.name != "nt" and (
        info.st_uid != os.getuid() or info.st_mode & 0o077
    ):
        raise PermissionError("sandbox settings directory must be private")


def _read_environment(path: Path) -> dict[str, str]:
    # Existing files must not be symlinks, junctions, or accessible by others.
    _check_directory(path.parent.parent)
    _check_directory(path.parent)
    try:
        entry = path.lstat()
    except FileNotFoundError:
        return {}
    if not stat.S_ISREG(entry.st_mode) or getattr(
        entry, "st_file_attributes", 0
    ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise PermissionError("sandbox settings file must not be a link")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16384:
            raise PermissionError("invalid sandbox settings file")
        if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise PermissionError("sandbox settings file must be private")
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            fd = -1
            data = json.load(stream)
    finally:
        if fd != -1:
            os.close(fd)
    if not isinstance(data, dict) or set(data) != {"environment"}:
        raise ValueError("invalid sandbox settings schema")
    return _validate_environment(data["environment"])


def effective_environment(root: Path, scope: TrustedSandboxScope) -> dict[str, str]:
    """Apply the user profile and then the session-specific overrides."""
    user = _read_environment(settings_path(root, scope, "user"))
    session = _read_environment(settings_path(root, scope, "session"))
    return {**user, **session}


def save_environment(
    root: Path, scope: TrustedSandboxScope, level: str, environment: dict[str, str]
) -> Path:
    """Trusted-host settings API. Never call from a sandbox tool handler."""
    checked = _validate_environment(environment)
    path = settings_path(root, scope, level)
    # The existing UAG data root may be shared by other UAG features and
    # need not be mode 0700. The new settings subtree must be private.
    parent = path.parent.parent.parent
    if parent.exists() or parent.is_symlink():
        _check_directory(parent, require_private=False)
    else:
        parent.mkdir(mode=0o700)
    for directory in (path.parent.parent, path.parent):
        if directory.exists() or directory.is_symlink():
            _check_directory(directory)
        else:
            directory.mkdir(mode=0o700)
    if path.exists() or path.is_symlink():
        # Reject a symlink even on platforms without O_NOFOLLOW.
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise PermissionError("sandbox settings target must be a regular file")
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    serialized = json.dumps({"environment": checked}, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > 16384:
        raise ValueError("sandbox settings file exceeds 16 KiB")
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(serialized)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path

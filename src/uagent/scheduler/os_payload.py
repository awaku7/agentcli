from __future__ import annotations

import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Any

from ..utils.paths import get_state_dir

_PAYLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_MAX_PAYLOAD_BYTES = 256_000
_MAX_TEXT_CHARS = 64_000


def scheduled_payload_directory() -> Path:
    """Return the private directory used for one-shot OS scheduler payloads."""
    return get_state_dir() / "scheduled_payloads"


def _payload_dir(directory: str | Path | None = None) -> Path:
    path = Path(directory).absolute() if directory else scheduled_payload_directory()
    if path.name != "scheduled_payloads":
        raise ValueError("invalid scheduled payload directory")
    if path.exists():
        resolved = path.resolve(strict=True)
        if resolved.name != "scheduled_payloads" or not resolved.is_dir():
            raise ValueError("invalid scheduled payload directory")
        if os.name != "nt" and stat.S_IMODE(resolved.stat().st_mode) & 0o077:
            raise ValueError("scheduled payload directory permissions are too broad")
        return resolved
    return path


def _payload_path(payload_id: str, directory: str | Path | None = None) -> Path:
    value = str(payload_id or "").strip().lower()
    if not _PAYLOAD_ID_RE.fullmatch(value):
        raise ValueError("invalid scheduled payload ID")
    return _payload_dir(directory) / f"{value}.json"


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message", "")
    prompt = payload.get("on_timeout_prompt", "")
    workdir = payload.get("workdir", "")
    tools = payload.get("enable_tools", [])
    if not isinstance(message, str) or len(message) > _MAX_TEXT_CHARS:
        raise ValueError("invalid scheduled message")
    if not isinstance(prompt, str) or len(prompt) > _MAX_TEXT_CHARS:
        raise ValueError("invalid scheduled prompt")
    if not isinstance(workdir, str) or len(workdir) > 4096:
        raise ValueError("invalid scheduled working directory")
    if not isinstance(tools, list) or len(tools) > 256:
        raise ValueError("invalid scheduled tool list")
    if any(
        not isinstance(name, str) or not name.strip() or len(name) > 200
        for name in tools
    ):
        raise ValueError("invalid scheduled tool name")
    return {
        "version": 1,
        "message": message,
        "on_timeout_prompt": prompt,
        "workdir": workdir,
        "enable_tools": list(dict.fromkeys(name.strip() for name in tools)),
    }


def create_scheduled_payload(
    payload: dict[str, Any], *, payload_id: str | None = None
) -> str:
    """Persist a one-shot payload; return only its opaque ID to the OS scheduler."""
    document = _normalize_payload(payload)
    directory = scheduled_payload_directory()
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("scheduled payload directory must be a real directory")
    directory = directory.resolve(strict=True)
    if os.name != "nt":
        os.chmod(directory, stat.S_IRWXU)
    payload_id = str(payload_id or secrets.token_hex(16)).lower()
    path = _payload_path(payload_id, directory)
    data = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(data) > _MAX_PAYLOAD_BYTES:
        raise ValueError("scheduled payload exceeds size limit")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    return payload_id


def delete_scheduled_payload(
    payload_id: str, directory: str | Path | None = None
) -> bool:
    try:
        _payload_path(payload_id, directory).unlink()
        return True
    except FileNotFoundError:
        return False


def consume_scheduled_payload(
    payload_id: str, directory: str | Path | None = None
) -> dict[str, Any]:
    """Atomically consume a one-shot payload so concurrent/replayed launches fail."""
    source = _payload_path(payload_id, directory)
    claimed = source.with_name(f".{source.stem}.{secrets.token_hex(8)}.claimed")
    try:
        os.replace(source, claimed)
    except FileNotFoundError as exc:
        raise ValueError("scheduled payload is missing or already consumed") from exc
    try:
        if claimed.stat().st_size > _MAX_PAYLOAD_BYTES:
            raise ValueError("scheduled payload exceeds size limit")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(claimed, flags)
        try:
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(_MAX_PAYLOAD_BYTES + 1)
        finally:
            pass
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, dict) or document.get("version") != 1:
            raise ValueError("unsupported scheduled payload")
        return _normalize_payload(document)
    finally:
        claimed.unlink(missing_ok=True)

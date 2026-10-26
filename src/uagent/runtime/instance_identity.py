"""Stable identity for one UAG installation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from ..env_utils import env_get
from ..utils.paths import get_state_dir

_INSTANCE_ID_FILENAME = "instance_id"
_MAX_INSTANCE_NAME_LENGTH = 128


def _normalize_uuid(value: str) -> str:
    try:
        return str(UUID(str(value).strip()))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("UAGENT_INSTANCE_ID must be a valid UUID") from exc


def _read_persisted_id(path: Path) -> str:
    try:
        value = path.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise RuntimeError("could not read the persisted UAG instance ID") from exc
    if not value:
        raise RuntimeError("the persisted UAG instance ID is empty")
    try:
        return _normalize_uuid(value)
    except ValueError as exc:
        raise RuntimeError("the persisted UAG instance ID is invalid") from exc


def get_instance_id() -> str:
    """Return a configured or persistent UUID identifying this UAG installation.

    ``UAGENT_INSTANCE_ID`` is intended for deployments that provision identity
    explicitly (for example, a container with a persistent identity volume).
    Otherwise, a UUID is generated once under the UAG state directory. The
    temporary-file plus hard-link publication prevents concurrent first starts
    from returning different IDs.
    """
    configured = env_get("UAGENT_INSTANCE_ID")
    if configured:
        return _normalize_uuid(configured)

    identity_path = get_state_dir() / _INSTANCE_ID_FILENAME
    if identity_path.exists():
        return _read_persisted_id(identity_path)

    identity_path.parent.mkdir(parents=True, exist_ok=True)
    generated = str(uuid4())
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="ascii",
            dir=identity_path.parent,
            prefix=".instance_id-",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(generated + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, identity_path)
            try:
                identity_path.chmod(0o600)
            except OSError:
                # Windows and some filesystems do not expose POSIX permissions.
                pass
            return generated
        except FileExistsError:
            return _read_persisted_id(identity_path)
    except OSError as exc:
        raise RuntimeError("could not persist the UAG instance ID") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def get_instance_name(instance_id: str | None = None) -> str:
    """Return a safe display name; it is not used as an identity or secret."""
    configured = str(env_get("UAGENT_INSTANCE_NAME", "") or "").strip()
    if configured:
        if len(configured) > _MAX_INSTANCE_NAME_LENGTH or any(
            ord(char) < 32 or ord(char) == 127 for char in configured
        ):
            raise ValueError(
                "UAGENT_INSTANCE_NAME must be at most 128 printable characters"
            )
        return configured
    resolved_id = instance_id or get_instance_id()
    return f"uag-{resolved_id[:8]}"

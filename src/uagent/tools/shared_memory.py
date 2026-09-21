# tools/shared_memory.py
"""shared_memory utilities for managing shared long-term memory notes."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from ..env_utils import env_get
from typing import Any, Optional

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

DEFAULT_MAX_SHARED_MEMORY_BYTES = 200_000
SHARED_MEMORY_DISABLED_PATH = ""


def _get_base_log_dir() -> str:
    from uagent.utils.paths import get_log_dir

    return str(get_log_dir())


def _get_shared_memory_file() -> str:
    """Return the absolute path to the shared memory file, or '' if disabled."""
    env = env_get("UAGENT_SHARED_MEMORY_FILE")
    if env:
        return str(Path(env).expanduser().resolve())
    return SHARED_MEMORY_DISABLED_PATH


def is_enabled() -> bool:
    """Shared memory is enabled only when UAGENT_SHARED_MEMORY_FILE is set."""
    return bool(env_get("UAGENT_SHARED_MEMORY_FILE"))


def get_shared_memory_file() -> str:
    """Return the absolute path to the shared memory file."""
    return _get_shared_memory_file()


def _resolve_project(project: str = "") -> str:
    if project.strip():
        return project.strip()
    from ..runtime.memory_scope import resolve_memory_project

    return resolve_memory_project()


def get_max_bytes() -> int:
    env = env_get("UAGENT_MAX_SHARED_MEMORY_BYTES")
    if env:
        try:
            v = int(env)
            if v > 0:
                return v
        except Exception:
            pass
    return DEFAULT_MAX_SHARED_MEMORY_BYTES


def append_shared_memory(note: str, *, owner: str = "", project: str = "") -> None:
    """Append a structured record to the shared memory file."""
    from ..runtime.memory_scope import resolve_memory_owner

    owner = resolve_memory_owner(owner)
    project = _resolve_project(project)
    path = _get_shared_memory_file()
    if not path:
        return

    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        record = {
            "schema_version": 2,
            "memory_id": uuid.uuid4().hex,
            "created_at": now,
            "updated_at": now,
            "ts": now,
            "note": note,
            "owner": owner,
            "project": project,
            "kind": "note",
            "revision": 1,
            "status": "active",
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_shared_memory_raw(max_bytes: Optional[int] = None) -> str:
    """Return the raw JSONL content of the shared memory (truncated)."""
    path = _get_shared_memory_file()
    if not path:
        return _(
            "msg.disabled",
            default="(shared memory is disabled; set UAGENT_SHARED_MEMORY_FILE to enable it)",
        )

    if max_bytes is None:
        max_bytes = get_max_bytes()

    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes + 1)
    except FileNotFoundError:
        return _("msg.no_shared_memory", default="(no shared memory yet)")
    except Exception as e:
        return _("err.load", default="[shared_memory error] {err_type}: {err}").format(
            err_type=type(e).__name__, err=str(e)
        )

    truncated_note = ""
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated_note = _(
            "msg.truncated",
            default="\n[shared_memory truncated: limited to {max_bytes} bytes]",
        ).format(max_bytes=max_bytes)

    text = data.decode("utf-8", errors="replace")
    return text + truncated_note


def load_shared_memory_records() -> list[dict[str, Any]]:
    """Parse JSONL into a list of dicts. Broken lines are skipped."""
    path = _get_shared_memory_file()
    if not path:
        return []

    records: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict) and "note" in obj:
                    records.append(obj)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return records

# tools/shared_memory.py
"""shared_memory utilities for managing shared long-term memory notes."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

DEFAULT_MAX_SHARED_MEMORY_BYTES = 200_000


def _get_base_log_dir() -> str:
    from uagent.utils.paths import get_log_dir

    return str(get_log_dir())


def _get_shared_memory_file() -> str:
    env = os.environ.get("UAGENT_SHARED_MEMORY_FILE")
    if env:
        return str(Path(env).expanduser().resolve())
    return os.path.join(_get_base_log_dir(), "scheck_shared_memory.jsonl")


def is_enabled() -> bool:
    return True


def get_shared_memory_file() -> str:
    """Return the absolute path to the shared memory file."""
    return _get_shared_memory_file()


def get_max_bytes() -> int:
    env = os.environ.get("UAGENT_MAX_SHARED_MEMORY_BYTES")
    if env:
        try:
            v = int(env)
            if v > 0:
                return v
        except Exception:
            pass
    return DEFAULT_MAX_SHARED_MEMORY_BYTES


def append_shared_memory(note: str) -> None:
    """Append a record to the shared memory file."""
    path = _get_shared_memory_file()
    if not path:
        return

    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": time.time(), "note": note}
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
        return f"[shared_memory error] {type(e).__name__}: {e}"

    truncated_note = ""
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated_note = _(
            "msg.truncated",
            default="\n[shared_memory truncated: limited to {max_bytes} bytes]",
        ).format(max_bytes=max_bytes)

    text = data.decode("utf-8", errors="replace")
    return text + truncated_note


def load_shared_memory_records() -> List[Dict[str, Any]]:
    """Parse JSONL into a list of dicts. Broken lines are skipped."""
    path = _get_shared_memory_file()
    if not path:
        return []

    records: List[Dict[str, Any]] = []
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

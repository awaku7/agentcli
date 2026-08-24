# tools/long_memory.py
"""Long-term memory utilities."""

from __future__ import annotations

import json
import os
from ..env_utils import env_get
import time
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _get_base_log_dir() -> str:
    from uagent.utils.paths import get_log_dir

    return str(get_log_dir())


def _use_sqlite() -> bool:
    return (env_get("UAGENT_MEMORY_BACKEND") or "sqlite").strip().lower() == "sqlite"


def _sqlite_path() -> str:
    return env_get("UAGENT_MEMORY_DB") or os.path.join(
        _get_base_log_dir(), "memory.sqlite3"
    )


def get_memory_file_path() -> str:
    """Return the resolved path to the personal long-memory JSONL file."""
    base_log_dir = _get_base_log_dir()
    return env_get("UAGENT_MEMORY_FILE") or os.path.join(
        base_log_dir, "scheck_memory.jsonl"
    )


def get_max_memory_bytes() -> int:
    return 200_000


def append_long_memory(note: str) -> None:
    """Append one personal memory record."""
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                store.append(note)
            finally:
                store.close()
        except Exception:
            pass
        return
    memory_file = get_memory_file_path()
    try:
        dirpath = os.path.dirname(memory_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        record = {"ts": time.time(), "note": note}
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_long_memory_raw() -> str:
    """Load the JSONL content as raw text (truncated)."""
    memory_file = get_memory_file_path()
    max_bytes = get_max_memory_bytes()

    try:
        with open(memory_file, encoding="utf-8") as f:
            data = f.read(max_bytes + 1)
    except FileNotFoundError:
        return _("msg.no_memory", default="(no long-term memory yet)")
    except Exception as e:
        return _("err.load", default="[long_memory error] {err_type}: {err}").format(
            err_type=type(e).__name__, err=str(e)
        )

    truncated_note = ""
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated_note = _(
            "msg.truncated",
            default="\n[long_memory truncated: limited to {max_bytes} chars]",
        ).format(max_bytes=max_bytes)

    return data + truncated_note


def load_long_memory_records() -> list[dict[str, Any]]:
    """Load personal memory records from the configured backend."""
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                return [
                    {"ts": row["created_at"], "note": row["note"]}
                    for row in store.records()
                ]
            finally:
                store.close()
        except Exception:
            return []
    memory_file = get_memory_file_path()
    records: list[dict[str, Any]] = []
    try:
        with open(memory_file, encoding="utf-8") as f:
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


def update_long_memory_entry(index: int, note: str) -> bool:
    """Update one record by index. Returns True on success."""
    if _use_sqlite():
        records = load_long_memory_records()
        if index < 0 or index >= len(records):
            return False
        records[index] = {"ts": time.time(), "note": note}
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                store.replace(records)
            finally:
                store.close()
            return True
        except Exception:
            return False
    records = load_long_memory_records()
    if index < 0 or index >= len(records):
        return False
    memory_file = get_memory_file_path()
    try:
        records[index] = {"ts": time.time(), "note": note}
        dirpath = os.path.dirname(memory_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(memory_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        return False
    return True


def delete_long_memory_entry(index: int) -> bool:
    """Delete one record by index. Returns True on success."""
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                return store.delete(index)
            finally:
                store.close()
        except Exception:
            return False
    records = load_long_memory_records()
    if index < 0 or index >= len(records):
        return False
    memory_file = get_memory_file_path()
    try:
        records.pop(index)
        dirpath = os.path.dirname(memory_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(memory_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        return False
    return True

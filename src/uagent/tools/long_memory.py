# tools/long_memory.py
"""Long-term memory utilities."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from ..env_utils import env_get

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

JSONL_SCHEMA_VERSION = 2


class MemoryMigrationError(RuntimeError):
    """Raised when a JSONL migration cannot be completed without data loss."""


def _get_base_log_dir() -> str:
    from uagent.utils.paths import get_log_dir

    return str(get_log_dir())


def _use_sqlite() -> bool:
    return (env_get("UAGENT_MEMORY_BACKEND") or "sqlite").strip().lower() == "sqlite"


def is_sqlite_backend() -> bool:
    """Return whether personal memory is configured to use SQLite."""
    return _use_sqlite()


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


def append_long_memory(note: str) -> bool:
    """Append one personal memory record and report whether it was saved."""
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                store.append(note)
            finally:
                store.close()
            return True
        except Exception:
            return False
    memory_file = get_memory_file_path()
    try:
        dirpath = os.path.dirname(memory_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        now = time.time()
        record = {
            "schema_version": JSONL_SCHEMA_VERSION,
            "memory_id": uuid.uuid4().hex,
            "created_at": now,
            "updated_at": now,
            "ts": now,
            "note": note,
            "kind": "note",
            "revision": 1,
            "status": "active",
        }
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def _legacy_jsonl_memory_id(record: dict[str, Any], index: int) -> str:
    payload = json.dumps(
        {
            "index": index,
            "created_at": record.get("created_at", record.get("ts")),
            "note": str(record.get("note") or ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return "legacy-jsonl-" + hashlib.sha256(payload).hexdigest()[:32]


def _normalize_jsonl_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    note = str(record.get("note") or "").strip()
    try:
        schema_version = int(record.get("schema_version") or 0)
    except (TypeError, ValueError):
        schema_version = 0
    is_legacy = schema_version < JSONL_SCHEMA_VERSION or not record.get("memory_id")
    if not note:
        raise MemoryMigrationError(f"record {index} has no non-empty note")
    created_at = record.get("created_at", record.get("ts"))
    if created_at is None:
        created_at = time.time()
    try:
        revision = max(1, int(record.get("revision") or 1))
    except (TypeError, ValueError):
        revision = 1
    normalized = dict(record)
    normalized.update(
        {
            "schema_version": JSONL_SCHEMA_VERSION,
            "memory_id": str(
                record.get("memory_id") or _legacy_jsonl_memory_id(record, index)
            ),
            "created_at": created_at,
            "updated_at": record.get("updated_at", created_at),
            "ts": record.get("ts", created_at),
            "note": note,
            "kind": str(record.get("kind") or "note"),
            "revision": revision,
            "status": str(record.get("status") or "active"),
        }
    )
    if is_legacy and not normalized.get("source"):
        normalized["source"] = "legacy_jsonl"
    return normalized


def migrate_long_memory_jsonl(
    path: str | os.PathLike[str] | None = None, *, backup: bool = True
) -> dict[str, Any]:
    """Migrate legacy JSONL records atomically to the structured schema.

    The operation is explicit: normal reads never rewrite the memory file.
    Invalid non-empty lines abort before the original file is modified.
    """
    memory_path = Path(path or get_memory_file_path()).expanduser()
    if not memory_path.exists():
        return {
            "path": str(memory_path),
            "changed": False,
            "record_count": 0,
            "backup_path": None,
        }

    raw_lines = memory_path.read_text(encoding="utf-8").splitlines()
    normalized_records: list[dict[str, Any]] = []
    changed = False
    for index, raw_line in enumerate(raw_lines):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except (TypeError, ValueError) as exc:
            raise MemoryMigrationError(f"invalid JSON at line {index + 1}") from exc
        if not isinstance(record, dict):
            raise MemoryMigrationError(f"record {index} is not an object")
        normalized = _normalize_jsonl_record(record, index)
        normalized_records.append(normalized)
        if json.dumps(normalized, ensure_ascii=False, sort_keys=True) != json.dumps(
            record, ensure_ascii=False, sort_keys=True
        ):
            changed = True

    if not changed:
        return {
            "path": str(memory_path),
            "changed": False,
            "record_count": len(normalized_records),
            "backup_path": None,
        }

    backup_path: str | None = None
    if backup:
        candidate = memory_path.with_name(memory_path.name + ".bak")
        if candidate.exists():
            candidate = memory_path.with_name(
                memory_path.name + f".bak.{int(time.time())}"
            )
        shutil.copy2(memory_path, candidate)
        backup_path = str(candidate)

    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=memory_path.parent,
            prefix=memory_path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = stream.name
            for record in normalized_records:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, memory_path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)

    return {
        "path": str(memory_path),
        "changed": True,
        "record_count": len(normalized_records),
        "backup_path": backup_path,
    }


def load_long_memory_raw() -> str:
    """Load the configured personal-memory backend as bounded JSONL text."""
    max_bytes = get_max_memory_bytes()
    try:
        if _use_sqlite():
            records = load_long_memory_records()
            if not records:
                return _("msg.no_memory", default="(no long-term memory yet)")
            data = "".join(
                json.dumps(record, ensure_ascii=False) + "\n" for record in records
            )
        else:
            memory_file = get_memory_file_path()
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
                    {
                        **row,
                        "ts": row.get("created_at", row.get("ts")),
                    }
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
        target = records[index]
        memory_id = str(target.get("memory_id") or "")
        if not memory_id:
            return False
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                updated = store.update_by_id(
                    memory_id,
                    note,
                    expected_revision=int(target.get("revision") or 1),
                )
            finally:
                store.close()
            return updated is not None
        except Exception:
            return False
    records = load_long_memory_records()
    if index < 0 or index >= len(records):
        return False
    memory_file = get_memory_file_path()
    try:
        updated = dict(records[index])
        updated["ts"] = time.time()
        updated["note"] = note
        updated["revision"] = int(updated.get("revision") or 1) + 1
        updated["status"] = "active"
        records[index] = updated
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


def vacuum_long_memory() -> bool:
    """Reclaim unused pages in the SQLite personal-memory database."""
    if not _use_sqlite():
        return False
    try:
        from ..runtime.memory_store import open_memory_store

        store = open_memory_store(_sqlite_path())
        try:
            store.vacuum()
        finally:
            store.close()
        return True
    except Exception:
        return False

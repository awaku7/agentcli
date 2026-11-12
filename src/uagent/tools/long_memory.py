# tools/long_memory.py
"""Long-term memory utilities."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from ..env_utils import env_get

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

JSONL_SCHEMA_VERSION = 2
_MIGRATION_MISSING_NOTE = "missing_note"
_MIGRATION_INVALID_JSON = "invalid_json"
_MIGRATION_NOT_OBJECT = "not_object"


class MemoryMigrationError(RuntimeError):
    """Raised when a JSONL migration cannot be completed without data loss."""

    def __init__(self, code: str, *, index: int):
        self.code = code
        self.index = index
        super().__init__(code)


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


def _resolve_project(project: str = "") -> str:
    if project.strip():
        return project.strip()
    from ..runtime.memory_scope import resolve_memory_project

    return resolve_memory_project()


#: Upper bound for one memory note saved through the checked save path.
NOTE_MAX_CHARS = 1000

_SECRET_LABEL_RE = re.compile(
    r"(password|passwd|pwd|secret|private[_\s-]?key|api[_\s-]?key|access[_\s-]?token|auth[_\s-]?token)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_SECRET_SHAPE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def looks_like_secret(text: str) -> bool:
    """Return True when a note clearly carries a credential value.

    The check is deliberately conservative: it only matches labelled
    secret assignments and well-known key shapes, so ordinary notes that
    merely mention passwords or tokens are not rejected.
    """
    value = str(text or "")
    return bool(_SECRET_LABEL_RE.search(value) or _SECRET_SHAPE_RE.search(value))


def _note_key(text: str) -> str:
    """Normalize a note for duplicate comparison (NFKC, casefold, no punctuation)."""
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return "".join(
        char for char in normalized if not unicodedata.category(char).startswith("P")
    ).strip()


def _is_active(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or "active").strip().lower()
    return status in {"", "active"}


def _env_disabled(name: str) -> bool:
    return (env_get(name) or "").strip().lower() in ("0", "false", "no", "off")


def tool_save_enabled() -> bool:
    """Whether the agent-facing memory write tools are offered at all.

    Opt out per feature with ``UAGENT_MEMORY_TOOL_SAVE=0`` (or everything
    memory-related with the master ``UAGENT_MEMORY=0``). Read access via
    get_long_memory is not affected.
    """
    if _env_disabled("UAGENT_MEMORY"):
        return False
    return not _env_disabled("UAGENT_MEMORY_TOOL_SAVE")


def save_long_memory(
    note: str,
    *,
    owner: str = "",
    project: str = "",
    source: str = "",
    source_id: str = "",
) -> dict[str, Any]:
    """Save one note through the checked save path used by agent-facing writers.

    Returns a result dict with ``saved`` plus a ``reason`` of ``saved``,
    ``duplicate``, ``secret``, ``too_long``, ``empty`` or ``error`` and the
    ``memory_id`` when a record exists. The checks keep credentials and
    exact re-saves out of the store; ``source``/``source_id`` record the
    provenance and make repeated saves of the same origin idempotent.
    """
    from ..runtime.memory_scope import resolve_memory_owner

    text = str(note or "").strip()
    if not text:
        return {"saved": False, "reason": "empty", "memory_id": ""}
    if len(text) > NOTE_MAX_CHARS:
        return {"saved": False, "reason": "too_long", "memory_id": ""}
    if looks_like_secret(text):
        return {"saved": False, "reason": "secret", "memory_id": ""}

    owner = resolve_memory_owner(owner)
    project = _resolve_project(project)
    key = _note_key(text)
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                if source_id:
                    for record in store.records(include_inactive=True):
                        if str(record.get("source_id") or "") == source_id:
                            if _is_active(record):
                                return {
                                    "saved": False,
                                    "reason": "duplicate",
                                    "memory_id": str(record.get("memory_id") or ""),
                                }
                            return {
                                "saved": False,
                                "reason": "deleted",
                                "memory_id": str(record.get("memory_id") or ""),
                            }
                for record in store.records():
                    if _note_key(str(record.get("note") or "")) == key:
                        return {
                            "saved": False,
                            "reason": "duplicate",
                            "memory_id": str(record.get("memory_id") or ""),
                        }
                record = store.append(
                    text,
                    owner=owner,
                    project=project,
                    source=source,
                    source_id=source_id,
                )
                return {
                    "saved": True,
                    "reason": "saved",
                    "memory_id": str(record.get("memory_id") or ""),
                }
            finally:
                store.close()
        except Exception:
            return {"saved": False, "reason": "error", "memory_id": ""}
    memory_file = get_memory_file_path()
    try:
        existing = _load_jsonl_records(include_deleted=True)
        if source_id:
            for record in existing:
                if str(record.get("source_id") or "") == source_id:
                    if _is_active(record):
                        return {
                            "saved": False,
                            "reason": "duplicate",
                            "memory_id": str(record.get("memory_id") or ""),
                        }
                    return {
                        "saved": False,
                        "reason": "deleted",
                        "memory_id": str(record.get("memory_id") or ""),
                    }
        for record in existing:
            if _is_active(record) and _note_key(str(record.get("note") or "")) == key:
                return {
                    "saved": False,
                    "reason": "duplicate",
                    "memory_id": str(record.get("memory_id") or ""),
                }
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
            "note": text,
            "owner": owner,
            "project": project,
            "kind": "note",
            "source": source,
            "source_id": source_id,
            "revision": 1,
            "status": "active",
        }
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"saved": True, "reason": "saved", "memory_id": record["memory_id"]}
    except Exception:
        return {"saved": False, "reason": "error", "memory_id": ""}


def append_long_memory(
    note: str, *, owner: str = "", project: str = "", source: str = ""
) -> bool:
    """Append one personal memory record and report whether it was saved.

    Kept for existing callers; new agent-facing writers should use
    :func:`save_long_memory` so duplicates and secrets are screened out.
    """
    from ..runtime.memory_scope import resolve_memory_owner

    owner = resolve_memory_owner(owner)
    project = _resolve_project(project)
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                store.append(note, owner=owner, project=project, source=source)
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
            "owner": owner,
            "project": project,
            "kind": "note",
            "source": source,
            "source_id": "",
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
        raise MemoryMigrationError(_MIGRATION_MISSING_NOTE, index=index)
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
            raise MemoryMigrationError(
                _MIGRATION_INVALID_JSON, index=index + 1
            ) from exc
        if not isinstance(record, dict):
            raise MemoryMigrationError(_MIGRATION_NOT_OBJECT, index=index)
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
            records = _load_jsonl_records(include_deleted=False)
            if not records:
                return _("msg.no_memory", default="(no long-term memory yet)")
            data = "".join(
                json.dumps(record, ensure_ascii=False) + "\n" for record in records
            )
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


class MemoryLoadError(RuntimeError):
    """A backend read failed; the error message intentionally contains no data."""

    def __init__(self, cause_type: str):
        self.cause_type = cause_type
        super().__init__(cause_type)


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
        except Exception as exc:
            raise MemoryLoadError(type(exc).__name__) from None
    return _load_jsonl_records(include_deleted=False)


def _load_jsonl_records(*, include_deleted: bool) -> list[dict[str, Any]]:
    """Read JSONL memory rows, hiding tombstoned rows unless requested."""
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
                except Exception as exc:
                    raise MemoryLoadError(type(exc).__name__) from None
                if isinstance(obj, dict) and "note" in obj:
                    if include_deleted or _is_active(obj):
                        records.append(obj)
    except FileNotFoundError:
        pass
    except MemoryLoadError:
        raise
    except Exception as exc:
        raise MemoryLoadError(type(exc).__name__) from None
    return records


def _rewrite_jsonl_records(records: list[dict[str, Any]]) -> bool:
    """Rewrite the JSONL memory file with the full row set (incl. tombstones)."""
    memory_file = get_memory_file_path()
    try:
        dirpath = os.path.dirname(memory_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(memory_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        return False
    return True


def list_deleted_long_memory_records() -> list[dict[str, Any]]:
    """Return tombstoned records (status ``deleted``), newest first."""
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                records = store.records(include_inactive=True)
            finally:
                store.close()
        except Exception:
            return []
    else:
        try:
            records = _load_jsonl_records(include_deleted=True)
        except MemoryLoadError:
            return []
    deleted = [r for r in records if not _is_active(r)]
    deleted.sort(key=lambda r: float(r.get("updated_at") or r.get("ts") or 0))
    return deleted


def find_long_memory_by_id(memory_id: str) -> dict[str, Any] | None:
    """Return the active record for ``memory_id``, or None."""
    target = str(memory_id or "").strip()
    if not target:
        return None
    try:
        records = load_long_memory_records()
    except MemoryLoadError:
        return None
    for record in records:
        if str(record.get("memory_id") or "") == target:
            return record
    return None


def update_long_memory_entry(index: int, note: str) -> bool:
    """Update one record by active-list index. Returns True on success."""
    try:
        records = load_long_memory_records()
    except MemoryLoadError:
        return False
    if index < 0 or index >= len(records):
        return False
    memory_id = str(records[index].get("memory_id") or "")
    if not memory_id:
        return False
    return bool(update_long_memory_by_id(memory_id, note)["saved"])


def update_long_memory_by_id(memory_id: str, note: str) -> dict[str, Any]:
    """Replace the text of one active record, addressed by memory_id.

    Returns a result dict like :func:`save_long_memory` (``saved`` is True
    when the record now holds the new text). Secret-looking replacements
    are rejected with reason ``secret``.
    """
    text = str(note or "").strip()
    if not text:
        return {"saved": False, "reason": "empty", "memory_id": ""}
    if len(text) > NOTE_MAX_CHARS:
        return {"saved": False, "reason": "too_long", "memory_id": ""}
    if looks_like_secret(text):
        return {"saved": False, "reason": "secret", "memory_id": ""}
    target = find_long_memory_by_id(memory_id)
    if target is None:
        return {"saved": False, "reason": "not_found", "memory_id": ""}
    target_id = str(target.get("memory_id") or "")
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                updated = store.update_by_id(
                    target_id,
                    text,
                    expected_revision=int(target.get("revision") or 1),
                )
            finally:
                store.close()
            if updated is None:
                return {"saved": False, "reason": "not_found", "memory_id": ""}
            return {"saved": True, "reason": "saved", "memory_id": target_id}
        except Exception:
            return {"saved": False, "reason": "error", "memory_id": ""}
    records = _load_jsonl_records(include_deleted=True)
    for record in records:
        if str(record.get("memory_id") or "") == target_id and _is_active(record):
            record["note"] = text
            record["updated_at"] = time.time()
            record["ts"] = record["updated_at"]
            record["revision"] = int(record.get("revision") or 1) + 1
            if not _rewrite_jsonl_records(records):
                return {"saved": False, "reason": "error", "memory_id": ""}
            return {"saved": True, "reason": "saved", "memory_id": target_id}
    return {"saved": False, "reason": "not_found", "memory_id": ""}


def delete_long_memory_by_id(memory_id: str, *, core: Any | None = None) -> bool:
    """Tombstone one active record by memory_id.

    The row stays in the store with status ``deleted`` so the deletion can
    be undone with :func:`restore_long_memory_by_id`; projections stop
    using it immediately and the forget propagation invalidates any
    in-flight snapshot.
    """
    target = find_long_memory_by_id(memory_id)
    if target is None:
        return False
    target_id = str(target.get("memory_id") or "")
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                deleted = store.tombstone_by_id(
                    target_id,
                    expected_revision=int(target.get("revision") or 1),
                )
            finally:
                store.close()
        except Exception:
            return False
        if deleted:
            _propagate_memory_forget(core)
        return deleted
    records = _load_jsonl_records(include_deleted=True)
    for record in records:
        if str(record.get("memory_id") or "") == target_id and _is_active(record):
            record["status"] = "deleted"
            record["updated_at"] = time.time()
            record["revision"] = int(record.get("revision") or 1) + 1
            if not _rewrite_jsonl_records(records):
                return False
            _propagate_memory_forget(core)
            return True
    return False


def restore_long_memory_by_id(memory_id: str) -> bool:
    """Undo a tombstone, returning the record to active status."""
    target_id = str(memory_id or "").strip()
    if not target_id:
        return False
    if _use_sqlite():
        try:
            from ..runtime.memory_store import open_memory_store

            store = open_memory_store(_sqlite_path())
            try:
                return store.restore_by_id(target_id)
            finally:
                store.close()
        except Exception:
            return False
    records = _load_jsonl_records(include_deleted=True)
    for record in records:
        if str(record.get("memory_id") or "") == target_id and not _is_active(record):
            record["status"] = "active"
            record["updated_at"] = time.time()
            record["revision"] = int(record.get("revision") or 1) + 1
            return _rewrite_jsonl_records(records)
    return False


def _propagate_memory_forget(core: Any | None = None) -> None:
    """Best-effort invalidation of memory-derived runtime state."""
    try:
        from ..runtime.memory_forget import invalidate_memory_runtime

        invalidate_memory_runtime(core)
    except Exception:
        pass


def delete_long_memory_entry(index: int, *, core: Any | None = None) -> bool:
    """Tombstone one record by active-list index.

    Deletion is a tombstone (see :func:`delete_long_memory_by_id`), not a
    physical removal, so it can be undone and re-learning paths can still
    see that the content was deliberately forgotten.
    """
    try:
        records = load_long_memory_records()
    except MemoryLoadError:
        return False
    if index < 0 or index >= len(records):
        return False
    memory_id = str(records[index].get("memory_id") or "")
    if not memory_id:
        return False
    return delete_long_memory_by_id(memory_id, core=core)


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

"""SQLite persistence for structured personal-memory records."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


class MemoryStoreConflictError(RuntimeError):
    """Raised when an update does not match the record revision."""


class MemoryStore:
    """Small SQLite repository with stable IDs and revision-checked writes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=5.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS memory_metadata ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "memory_id TEXT, created_at REAL NOT NULL, updated_at REAL, "
            "note TEXT NOT NULL, owner TEXT, project TEXT, "
            "kind TEXT NOT NULL DEFAULT 'note', source TEXT, source_id TEXT, "
            "revision INTEGER NOT NULL DEFAULT 1, "
            "status TEXT NOT NULL DEFAULT 'active', supersedes_id TEXT)"
        )
        columns = {
            str(row["name"])
            for row in self.db.execute("PRAGMA table_info(memories)").fetchall()
        }
        additions = {
            "memory_id": "TEXT",
            "updated_at": "REAL",
            "owner": "TEXT",
            "project": "TEXT",
            "kind": "TEXT NOT NULL DEFAULT 'note'",
            "source": "TEXT",
            "source_id": "TEXT",
            "revision": "INTEGER NOT NULL DEFAULT 1",
            "status": "TEXT NOT NULL DEFAULT 'active'",
            "supersedes_id": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                self.db.execute(f"ALTER TABLE memories ADD COLUMN {name} {definition}")

        self.db.execute(
            "UPDATE memories SET memory_id = 'legacy-' || id "
            "WHERE memory_id IS NULL OR memory_id = ''"
        )
        self.db.execute(
            "UPDATE memories SET updated_at = created_at " "WHERE updated_at IS NULL"
        )
        self.db.execute(
            "UPDATE memories SET kind = 'note' WHERE kind IS NULL OR kind = ''"
        )
        self.db.execute(
            "UPDATE memories SET revision = 1 WHERE revision IS NULL OR revision < 1"
        )
        self.db.execute(
            "UPDATE memories SET status = 'active' "
            "WHERE status IS NULL OR status = ''"
        )
        self.db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_memory_id "
            "ON memories(memory_id)"
        )
        self.db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_source_id "
            "ON memories(source_id) WHERE source_id IS NOT NULL AND source_id <> ''"
        )
        self.db.execute(
            "INSERT OR IGNORE INTO memory_metadata(key, value) "
            "VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.db.execute(
            "UPDATE memory_metadata SET value = ? WHERE key = 'schema_version'",
            (str(SCHEMA_VERSION),),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _record_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        record = dict(row)
        record["ts"] = record.get("created_at")
        return record

    def _get_by_id(self, memory_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT id, memory_id, created_at, updated_at, note, owner, project, "
            "kind, source, source_id, revision, status, supersedes_id "
            "FROM memories WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        return self._record_from_row(row)

    def append(
        self,
        note: str,
        *,
        owner: str = "",
        project: str = "",
        kind: str = "note",
        source: str = "",
        source_id: str = "",
        supersedes_id: str = "",
    ) -> dict[str, Any]:
        """Append one record, or return the existing record for a source ID."""
        text = str(note or "")
        if not text:
            raise ValueError("note must not be empty")
        if source_id:
            existing = self.db.execute(
                "SELECT memory_id FROM memories WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if existing is not None:
                record = self._get_by_id(str(existing["memory_id"]))
                if record is not None:
                    return record

        memory_id = uuid.uuid4().hex
        now = time.time()
        try:
            self.db.execute(
                "INSERT INTO memories("
                "memory_id, created_at, updated_at, note, owner, project, kind, "
                "source, source_id, revision, status, supersedes_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'active', ?)",
                (
                    memory_id,
                    now,
                    now,
                    text,
                    str(owner or ""),
                    str(project or ""),
                    str(kind or "note"),
                    str(source or ""),
                    str(source_id or "") or None,
                    str(supersedes_id or "") or None,
                ),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            self.db.rollback()
            if source_id:
                existing = self.db.execute(
                    "SELECT memory_id FROM memories WHERE source_id = ?",
                    (source_id,),
                ).fetchone()
                if existing is not None:
                    record = self._get_by_id(str(existing["memory_id"]))
                    if record is not None:
                        return record
            raise
        except Exception:
            self.db.rollback()
            raise
        record = self._get_by_id(memory_id)
        if record is None:
            raise RuntimeError("memory insert did not produce a record")
        return record

    def records(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        where = "" if include_inactive else " WHERE status = 'active'"
        rows = self.db.execute(
            "SELECT id, memory_id, created_at, updated_at, note, owner, project, "
            "kind, source, source_id, revision, status, supersedes_id "
            "FROM memories" + where + " ORDER BY id"
        ).fetchall()
        return [self._record_from_row(row) for row in rows if row is not None]

    def get(self, memory_id: str) -> dict[str, Any] | None:
        return self._get_by_id(str(memory_id))

    def update_by_id(
        self,
        memory_id: str,
        note: str,
        *,
        expected_revision: int | None = None,
        owner: str | None = None,
        project: str | None = None,
        kind: str | None = None,
        source: str | None = None,
    ) -> dict[str, Any] | None:
        """Update one record atomically and increment its revision."""
        current = self._get_by_id(str(memory_id))
        if current is None or current.get("status") != "active":
            return None
        if expected_revision is not None and int(current.get("revision") or 0) != int(
            expected_revision
        ):
            raise MemoryStoreConflictError(f"memory revision conflict: {memory_id}")
        now = time.time()
        fields = {
            "note": str(note),
            "owner": current.get("owner", "") if owner is None else str(owner),
            "project": current.get("project", "") if project is None else str(project),
            "kind": current.get("kind", "note") if kind is None else str(kind),
            "source": current.get("source", "") if source is None else str(source),
        }
        next_revision = int(current.get("revision") or 0) + 1
        try:
            cursor = self.db.execute(
                "UPDATE memories SET note = ?, owner = ?, project = ?, kind = ?, "
                "source = ?, updated_at = ?, revision = ? "
                "WHERE memory_id = ? AND status = 'active' AND revision = ?",
                (
                    fields["note"],
                    fields["owner"],
                    fields["project"],
                    fields["kind"],
                    fields["source"],
                    now,
                    next_revision,
                    str(memory_id),
                    int(current.get("revision") or 0),
                ),
            )
            if cursor.rowcount != 1:
                self.db.rollback()
                raise MemoryStoreConflictError(f"memory revision conflict: {memory_id}")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._get_by_id(str(memory_id))

    def forget_by_id(
        self, memory_id: str, *, expected_revision: int | None = None
    ) -> bool:
        """Forget one record without reindexing any other record."""
        current = self._get_by_id(str(memory_id))
        if current is None:
            return False
        if expected_revision is not None and int(current.get("revision") or 0) != int(
            expected_revision
        ):
            raise MemoryStoreConflictError(f"memory revision conflict: {memory_id}")
        try:
            if expected_revision is None:
                cursor = self.db.execute(
                    "DELETE FROM memories WHERE memory_id = ?", (str(memory_id),)
                )
            else:
                cursor = self.db.execute(
                    "DELETE FROM memories WHERE memory_id = ? "
                    "AND status = 'active' AND revision = ?",
                    (str(memory_id), int(expected_revision)),
                )
            if cursor.rowcount != 1:
                self.db.rollback()
                raise MemoryStoreConflictError(f"memory revision conflict: {memory_id}")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True

    def replace(self, records: list[dict[str, object]]) -> None:
        """Compatibility rewrite preserving supplied stable IDs when possible."""
        incoming_ids: set[str] = set()
        for row in records:
            memory_id = str(row.get("memory_id") or "")
            note = str(row.get("note") or "")
            if not note:
                continue
            if memory_id:
                current = self._get_by_id(memory_id)
                if current is not None:
                    incoming_ids.add(memory_id)
                    self.update_by_id(
                        memory_id,
                        note,
                        expected_revision=int(current.get("revision") or 1),
                    )
                    continue
            created = self.append(note)
            incoming_ids.add(str(created["memory_id"]))

        existing_ids = {
            str(row["memory_id"])
            for row in self.db.execute(
                "SELECT memory_id FROM memories WHERE status = 'active'"
            ).fetchall()
        }
        for memory_id in existing_ids - incoming_ids:
            self.forget_by_id(memory_id)

    def delete(self, index: int) -> bool:
        rows = self.records()
        if index < 0 or index >= len(rows):
            return False
        return self.forget_by_id(
            str(rows[index]["memory_id"]),
            expected_revision=int(rows[index].get("revision") or 1),
        )

    def vacuum(self) -> None:
        """Reclaim unused SQLite pages after memory deletions."""
        self.db.execute("VACUUM")


def open_memory_store(path: str | Path) -> MemoryStore:
    return MemoryStore(path)


__all__ = [
    "MemoryStore",
    "MemoryStoreConflictError",
    "SCHEMA_VERSION",
    "open_memory_store",
]

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_memory_store_assigns_stable_ids_and_revisions(tmp_path: Path) -> None:
    from uagent.runtime.memory_store import MemoryStore, MemoryStoreConflictError

    store = MemoryStore(tmp_path / "memory.sqlite3")
    try:
        first = store.append("first", owner="alice", project="app", source_id="event-1")
        duplicate = store.append("ignored", source_id="event-1")
        second = store.append("second")

        assert first["memory_id"]
        assert first["memory_id"] == duplicate["memory_id"]
        assert first["note"] == "first"
        assert first["revision"] == 1

        updated = store.update_by_id(first["memory_id"], "updated", expected_revision=1)
        assert updated is not None
        assert updated["memory_id"] == first["memory_id"]
        assert updated["revision"] == 2
        assert updated["note"] == "updated"

        with pytest.raises(MemoryStoreConflictError):
            store.update_by_id(first["memory_id"], "stale", expected_revision=1)

        assert store.forget_by_id(first["memory_id"], expected_revision=2) is True
        assert [record["note"] for record in store.records()] == ["second"]
        assert store.get(second["memory_id"]) is not None
    finally:
        store.close()


def test_memory_store_migrates_legacy_rows_without_reindexing(tmp_path: Path) -> None:
    from uagent.runtime.memory_store import MemoryStore, SCHEMA_VERSION

    path = tmp_path / "legacy.sqlite3"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE memories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "created_at REAL NOT NULL, note TEXT NOT NULL)"
    )
    db.execute("INSERT INTO memories(created_at, note) VALUES (1, 'legacy')")
    db.commit()
    db.close()

    store = MemoryStore(path)
    try:
        records = store.records()
        assert len(records) == 1
        assert records[0]["memory_id"] == "legacy-1"
        assert records[0]["revision"] == 1
        assert records[0]["status"] == "active"
        version = store.db.execute(
            "SELECT value FROM memory_metadata WHERE key = 'schema_version'"
        ).fetchone()[0]
        assert int(version) == SCHEMA_VERSION
    finally:
        store.close()


def test_long_memory_index_update_preserves_other_sqlite_ids(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))

    assert long_memory.append_long_memory("first") is True
    assert long_memory.append_long_memory("second") is True
    before = long_memory.load_long_memory_records()

    assert long_memory.update_long_memory_entry(0, "updated") is True
    after = long_memory.load_long_memory_records()

    assert after[0]["note"] == "updated"
    assert after[0]["memory_id"] == before[0]["memory_id"]
    assert after[0]["revision"] == before[0]["revision"] + 1
    assert after[1]["memory_id"] == before[1]["memory_id"]

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_jsonl_migration_adds_stable_ids_atomically_and_is_idempotent(
    tmp_path: Path,
) -> None:
    from uagent.tools.long_memory import migrate_long_memory_jsonl

    path = tmp_path / "memory.jsonl"
    path.write_text(
        json.dumps({"ts": 1, "note": "legacy one"}, ensure_ascii=False)
        + "\n"
        + json.dumps(
            {
                "ts": 2,
                "note": "legacy two",
                "owner": "alice",
                "project": "app",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    first = migrate_long_memory_jsonl(path)
    assert first["changed"] is True
    assert first["record_count"] == 2
    assert first["backup_path"]
    assert Path(first["backup_path"]).exists()

    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert all(record["schema_version"] == 2 for record in records)
    assert all(record["memory_id"].startswith("legacy-jsonl-") for record in records)
    assert [record["note"] for record in records] == ["legacy one", "legacy two"]
    assert records[1]["owner"] == "alice"
    assert records[1]["project"] == "app"
    ids = [record["memory_id"] for record in records]

    second = migrate_long_memory_jsonl(path, backup=False)
    assert second["changed"] is False
    assert [
        json.loads(line)["memory_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
    ] == ids


def test_jsonl_migration_rejects_invalid_lines_without_modifying_original(
    tmp_path: Path,
) -> None:
    from uagent.tools.long_memory import MemoryMigrationError, migrate_long_memory_jsonl

    path = tmp_path / "memory.jsonl"
    original = '{"ts": 1, "note": "ok"}\nnot-json\n'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(MemoryMigrationError):
        migrate_long_memory_jsonl(path)

    assert path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "memory.jsonl.bak").exists()


def test_new_jsonl_records_use_structured_schema(tmp_path: Path, monkeypatch) -> None:
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp_path / "memory.jsonl"))
    assert long_memory.append_long_memory("new note") is True

    record = json.loads((tmp_path / "memory.jsonl").read_text(encoding="utf-8"))
    assert record["schema_version"] == 2
    assert record["memory_id"]
    assert record["revision"] == 1
    assert record["status"] == "active"

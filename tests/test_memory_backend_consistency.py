from __future__ import annotations

import json
from pathlib import Path


def test_get_long_memory_reads_sqlite_backend(repo_tmp_path: Path, monkeypatch) -> None:
    from uagent.tools.add_long_memory_tool import run_tool as add_long_memory
    from uagent.tools.get_long_memory_tool import run_tool as get_long_memory
    from uagent.tools.long_memory import load_long_memory_records

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(repo_tmp_path / "memory.sqlite3"))

    assert "saved" in add_long_memory({"note": "sqlite-note"}).lower()

    listed = load_long_memory_records()
    raw = get_long_memory({})
    raw_records = [json.loads(line) for line in raw.splitlines() if line.strip()]

    assert [record["note"] for record in raw_records] == [
        record["note"] for record in listed
    ]
    assert raw_records[0]["note"] == "sqlite-note"


def test_mem_delete_uses_same_sqlite_index_as_list_and_get(
    repo_tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools.add_long_memory_tool import run_tool as add_long_memory
    from uagent.tools.get_long_memory_tool import run_tool as get_long_memory
    from uagent.tools.long_memory import (
        delete_long_memory_entry,
        load_long_memory_records,
    )

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(repo_tmp_path / "memory.sqlite3"))

    add_long_memory({"note": "first"})
    add_long_memory({"note": "second"})
    add_long_memory({"note": "third"})

    assert delete_long_memory_entry(1) is True

    listed = load_long_memory_records()
    raw_records = [
        json.loads(line) for line in get_long_memory({}).splitlines() if line.strip()
    ]
    assert [record["note"] for record in listed] == ["first", "third"]
    assert [record["note"] for record in raw_records] == ["first", "third"]
    assert delete_long_memory_entry(2) is False


def test_mem_vacuum_is_manual_and_sqlite_only(repo_tmp_path: Path, monkeypatch) -> None:
    from uagent.tools.long_memory import vacuum_long_memory

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(repo_tmp_path / "memory.sqlite3"))
    assert vacuum_long_memory() is True

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    assert vacuum_long_memory() is False

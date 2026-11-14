from __future__ import annotations

from pathlib import Path

import pytest


def _use_jsonl(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp / "mem.jsonl"))


def _use_sqlite(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp / "memory.sqlite3"))


def _setup(backend: str, monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    if backend == "jsonl":
        _use_jsonl(monkeypatch, tmp)
    else:
        _use_sqlite(monkeypatch, tmp)


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_supersede_retires_old_note(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    old = long_memory.save_long_memory("住所は東京", source="tool")
    assert old["saved"] is True

    new = long_memory.save_long_memory(
        "住所は大阪", source="tool", supersedes_id=old["memory_id"]
    )
    assert new["saved"] is True
    assert new["superseded_id"] == old["memory_id"]

    active_notes = [
        str(r.get("note") or "") for r in long_memory.load_long_memory_records()
    ]
    assert "住所は大阪" in active_notes
    assert "住所は東京" not in active_notes

    new_record = [
        r
        for r in long_memory.load_long_memory_records()
        if str(r.get("memory_id") or "") == new["memory_id"]
    ][0]
    assert new_record.get("supersedes_id") == old["memory_id"]

    retired = [
        r
        for r in long_memory.list_deleted_long_memory_records()
        if str(r.get("memory_id") or "") == old["memory_id"]
    ]
    assert len(retired) == 1
    assert retired[0].get("status") == "superseded"


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_superseded_note_stays_retired_for_background_saves(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    old = long_memory.save_long_memory("住所は東京", source="tool")
    long_memory.save_long_memory(
        "住所は大阪", source="tool", supersedes_id=old["memory_id"]
    )

    relearned = long_memory.save_long_memory("住所は東京", source="consolidation")
    assert relearned["saved"] is False
    assert relearned["reason"] == "deleted"

    keys = long_memory.forgotten_note_keys()
    assert long_memory.note_key_for("住所は東京") in keys

    restated = long_memory.save_long_memory("住所は東京", source="tool")
    assert restated["saved"] is True


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_supersede_ignores_unknown_and_out_of_scope_targets(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    unknown = long_memory.save_long_memory(
        "趣味は読書", source="tool", supersedes_id="no-such-id"
    )
    assert unknown["saved"] is True
    assert unknown["superseded_id"] == ""

    in_a = long_memory.save_long_memory("担当はAプロジェクト", project="proj-a")
    assert in_a["saved"] is True
    in_b = long_memory.save_long_memory(
        "担当はBプロジェクト",
        project="proj-b",
        supersedes_id=in_a["memory_id"],
    )
    assert in_b["saved"] is True
    assert in_b["superseded_id"] == ""

    active_ids = {
        str(r.get("memory_id") or "") for r in long_memory.load_long_memory_records()
    }
    assert in_a["memory_id"] in active_ids


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_superseded_note_can_be_restored(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    old = long_memory.save_long_memory("住所は東京", source="tool")
    long_memory.save_long_memory(
        "住所は大阪", source="tool", supersedes_id=old["memory_id"]
    )
    assert long_memory.restore_long_memory_by_id(old["memory_id"]) is True
    active_notes = [
        str(r.get("note") or "") for r in long_memory.load_long_memory_records()
    ]
    assert "住所は東京" in active_notes


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_duplicate_save_can_still_supersede(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    _setup(backend, monkeypatch, repo_tmp_path)

    old = long_memory.save_long_memory("住所は東京", source="tool")
    new = long_memory.save_long_memory("住所は大阪", source="tool")
    assert new["saved"] is True

    # The replacement was saved earlier without naming its predecessor;
    # restating it with supersedes retires the old record anyway.
    again = long_memory.save_long_memory(
        "住所は大阪", source="tool", supersedes_id=old["memory_id"]
    )
    assert again["saved"] is False
    assert again["reason"] == "duplicate"
    assert again["memory_id"] == new["memory_id"]
    assert again["superseded_id"] == old["memory_id"]

    active_notes = [
        str(r.get("note") or "") for r in long_memory.load_long_memory_records()
    ]
    assert active_notes == ["住所は大阪"]

    # A note never supersedes itself.
    itself = long_memory.save_long_memory(
        "住所は大阪", source="tool", supersedes_id=new["memory_id"]
    )
    assert itself["reason"] == "duplicate"
    assert itself["superseded_id"] == ""
    active_notes = [
        str(r.get("note") or "") for r in long_memory.load_long_memory_records()
    ]
    assert active_notes == ["住所は大阪"]


def test_store_supersede_and_restore(tmp_path: Path) -> None:
    from uagent.runtime.memory_store import open_memory_store

    store = open_memory_store(str(tmp_path / "memory.sqlite3"))
    try:
        old = store.append("old fact")
        new = store.append("new fact", supersedes_id=str(old["memory_id"]))
        assert new["supersedes_id"] == old["memory_id"]
        assert store.supersede_by_id(str(old["memory_id"])) is True
        assert store.supersede_by_id(str(old["memory_id"])) is False
        active = {str(r["memory_id"]) for r in store.records()}
        assert str(old["memory_id"]) not in active
        assert str(new["memory_id"]) in active
        assert store.restore_by_id(str(old["memory_id"])) is True
        active = {str(r["memory_id"]) for r in store.records()}
        assert str(old["memory_id"]) in active
    finally:
        store.close()


def test_add_long_memory_tool_passes_supersedes(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import add_long_memory_tool, long_memory

    _use_sqlite(monkeypatch, repo_tmp_path)

    first = add_long_memory_tool.run_tool({"note": "勤務先はA社"})
    assert "memory_id" in first

    records = long_memory.load_long_memory_records()
    old_id = str(records[0]["memory_id"])

    second = add_long_memory_tool.run_tool(
        {"note": "勤務先はB社", "supersedes": old_id}
    )
    assert old_id in second
    active_notes = [
        str(r.get("note") or "") for r in long_memory.load_long_memory_records()
    ]
    assert active_notes == ["勤務先はB社"]

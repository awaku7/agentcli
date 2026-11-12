from __future__ import annotations

from pathlib import Path

import pytest


def _use_jsonl(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp / "mem.jsonl"))


def _use_sqlite(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp / "memory.sqlite3"))


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_save_duplicate_and_secret_screening(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    if backend == "jsonl":
        _use_jsonl(monkeypatch, repo_tmp_path)
    else:
        _use_sqlite(monkeypatch, repo_tmp_path)

    first = long_memory.save_long_memory("テストは pytest を使う", source="tool")
    assert first["saved"] is True
    assert first["memory_id"]

    again = long_memory.save_long_memory("テストは pytest を使う", source="tool")
    assert again["saved"] is False
    assert again["reason"] == "duplicate"
    assert again["memory_id"] == first["memory_id"]

    secret = long_memory.save_long_memory("api_key = sk-1234567890abcdefghij")
    assert secret["saved"] is False
    assert secret["reason"] == "secret"

    labelled = long_memory.save_long_memory("本番の password: hunter2")
    assert labelled["saved"] is False
    assert labelled["reason"] == "secret"

    mention_only = long_memory.save_long_memory("パスワードは保存しない方針")
    assert mention_only["saved"] is True

    too_long = long_memory.save_long_memory("あ" * (long_memory.NOTE_MAX_CHARS + 1))
    assert too_long["saved"] is False
    assert too_long["reason"] == "too_long"

    records = long_memory.load_long_memory_records()
    saved_notes = [str(r.get("note") or "") for r in records]
    assert "テストは pytest を使う" in saved_notes
    tool_records = [
        r for r in records if str(r.get("note")) == "テストは pytest を使う"
    ]
    assert tool_records[0].get("source") == "tool"


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_save_source_id_is_idempotent_even_after_delete(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    if backend == "jsonl":
        _use_jsonl(monkeypatch, repo_tmp_path)
    else:
        _use_sqlite(monkeypatch, repo_tmp_path)

    first = long_memory.save_long_memory(
        "マーカー由来のメモ", source="marker", source_id="msg-1"
    )
    assert first["saved"] is True

    dup = long_memory.save_long_memory(
        "マーカー由来のメモ", source="marker", source_id="msg-1"
    )
    assert dup["saved"] is False
    assert dup["reason"] == "duplicate"

    assert long_memory.delete_long_memory_by_id(first["memory_id"]) is True

    # Re-saving a deliberately forgotten note via the same origin must not
    # resurrect it.
    zombie = long_memory.save_long_memory(
        "マーカー由来のメモ", source="marker", source_id="msg-1"
    )
    assert zombie["saved"] is False
    assert zombie["reason"] == "deleted"
    assert long_memory.load_long_memory_records() == []


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_update_and_tombstone_restore_cycle(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    if backend == "jsonl":
        _use_jsonl(monkeypatch, repo_tmp_path)
    else:
        _use_sqlite(monkeypatch, repo_tmp_path)

    saved = long_memory.save_long_memory("勤務先はA社", source="tool")
    memory_id = saved["memory_id"]

    updated = long_memory.update_long_memory_by_id(memory_id, "勤務先はB社")
    assert updated["saved"] is True
    record = long_memory.find_long_memory_by_id(memory_id)
    assert record is not None
    assert record["note"] == "勤務先はB社"

    assert long_memory.delete_long_memory_by_id(memory_id) is True
    assert long_memory.find_long_memory_by_id(memory_id) is None
    assert long_memory.load_long_memory_records() == []
    # Deleting twice is a no-op failure, not an error.
    assert long_memory.delete_long_memory_by_id(memory_id) is False

    assert long_memory.restore_long_memory_by_id(memory_id) is True
    record = long_memory.find_long_memory_by_id(memory_id)
    assert record is not None
    assert record["note"] == "勤務先はB社"


def test_delete_entry_by_index_tombstones(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime.memory_store import open_memory_store
    from uagent.tools import long_memory

    _use_sqlite(monkeypatch, repo_tmp_path)
    long_memory.save_long_memory("残すメモ", source="tool")
    long_memory.save_long_memory("消すメモ", source="tool")

    assert long_memory.delete_long_memory_entry(1) is True
    notes = [str(r.get("note")) for r in long_memory.load_long_memory_records()]
    assert notes == ["残すメモ"]

    store = open_memory_store(str(repo_tmp_path / "memory.sqlite3"))
    try:
        all_records = store.records(include_inactive=True)
    finally:
        store.close()
    statuses = {str(r.get("note")): str(r.get("status")) for r in all_records}
    assert statuses["消すメモ"] == "deleted"
    assert statuses["残すメモ"] == "active"


def test_memory_tools_end_to_end_jsonl(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools.add_long_memory_tool import run_tool as add_tool
    from uagent.tools.delete_long_memory_tool import run_tool as delete_tool
    from uagent.tools.get_long_memory_tool import run_tool as get_tool
    from uagent.tools.update_long_memory_tool import run_tool as update_tool

    _use_jsonl(monkeypatch, repo_tmp_path)

    out = add_tool({"note": "好きな色は青"})
    assert "saved" in out
    records_text = get_tool({})
    assert "好きな色は青" in records_text

    from uagent.tools import long_memory

    memory_id = long_memory.load_long_memory_records()[0]["memory_id"]

    dup = add_tool({"note": "好きな色は青"})
    assert "already" in dup or "既に" in dup

    upd = update_tool({"memory_id": memory_id, "note": "好きな色は緑"})
    assert "updated" in upd
    assert "好きな色は緑" in get_tool({})

    missing = update_tool({"memory_id": "nope", "note": "x"})
    assert "error" in missing

    deleted = delete_tool({"memory_id": memory_id})
    assert "forgotten" in deleted or "忘れ" in deleted
    assert "好きな色は緑" not in get_tool({})

    missing_delete = delete_tool({"memory_id": memory_id})
    assert "error" in missing_delete


def test_tool_save_opt_out_switch(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory
    from uagent.tools.add_long_memory_tool import is_loadable

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.delenv("UAGENT_MEMORY_TOOL_SAVE", raising=False)
    monkeypatch.delenv("UAGENT_MEMORY", raising=False)
    assert long_memory.tool_save_enabled() is True
    assert is_loadable() is True

    monkeypatch.setenv("UAGENT_MEMORY_TOOL_SAVE", "0")
    assert long_memory.tool_save_enabled() is False
    assert is_loadable() is False

    monkeypatch.setenv("UAGENT_MEMORY_TOOL_SAVE", "1")
    monkeypatch.setenv("UAGENT_MEMORY", "0")
    assert long_memory.tool_save_enabled() is False


def test_marker_extraction_rules() -> None:
    from uagent.runtime.memory_marker import extract_memory_marker

    assert extract_memory_marker("remember: use pytest") == "use pytest"
    assert extract_memory_marker("Remember: use pytest") == "use pytest"
    assert extract_memory_marker("記憶：日本語で答える") == "日本語で答える"
    assert extract_memory_marker("please remember: use pytest") is None
    assert extract_memory_marker("remember:") is None
    assert extract_memory_marker("ordinary request") is None


def test_marker_save_via_store_and_replace_idempotency(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime.session_store import SessionStore
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    store = SessionStore(repo_tmp_path / "sessions.sqlite3")
    session = store.create_session(project="agentcli", entry_point="cli")

    store.append_message(session.session_id, "user", "remember: 返事は日本語で")
    records = long_memory.load_long_memory_records()
    assert [str(r.get("note")) for r in records] == ["返事は日本語で"]
    assert records[0].get("source") == "marker"
    assert len(store.drain_memory_notices()) == 1

    # Rewriting the same history must not duplicate the note or re-notify.
    store.replace_messages(
        session.session_id,
        [
            {"role": "user", "content": "remember: 返事は日本語で"},
            {"role": "assistant", "content": "はい"},
        ],
    )
    assert len(long_memory.load_long_memory_records()) == 1
    assert store.drain_memory_notices() == []

    # After the note is forgotten, a history rewrite must not resurrect it.
    memory_id = str(records[0].get("memory_id"))
    assert long_memory.delete_long_memory_by_id(memory_id) is True
    store.replace_messages(
        session.session_id,
        [
            {"role": "user", "content": "remember: 返事は日本語で"},
            {"role": "assistant", "content": "はい"},
        ],
    )
    assert long_memory.load_long_memory_records() == []
    store.close()


def test_marker_opt_out_switch(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime.memory_marker import marker_enabled, save_memory_marker

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.setenv("UAGENT_MEMORY_MARKER", "0")
    assert marker_enabled() is False
    assert save_memory_marker("remember: x") is None

    monkeypatch.setenv("UAGENT_MEMORY_MARKER", "1")
    monkeypatch.setenv("UAGENT_MEMORY", "0")
    assert marker_enabled() is False

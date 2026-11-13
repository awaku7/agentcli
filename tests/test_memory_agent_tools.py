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


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_marker_duplicate_binds_provenance_so_forget_sticks(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A note first saved through the tool, then repeated as a marker: the
    # duplicate rejection must still record the marker's source_id, or a
    # later history rewrite would resurrect the note after it is deleted.
    from uagent.runtime.memory_marker import marker_source_id
    from uagent.tools import long_memory

    if backend == "jsonl":
        _use_jsonl(monkeypatch, repo_tmp_path)
    else:
        _use_sqlite(monkeypatch, repo_tmp_path)

    note = "返事は日本語で"
    source_id = marker_source_id(note)
    first = long_memory.save_long_memory(note, source="tool")
    assert first["saved"] is True

    dup = long_memory.save_long_memory(note, source="marker", source_id=source_id)
    assert dup["saved"] is False
    assert dup["reason"] == "duplicate"

    assert long_memory.delete_long_memory_by_id(first["memory_id"]) is True

    replay = long_memory.save_long_memory(note, source="marker", source_id=source_id)
    assert replay["saved"] is False
    assert replay["reason"] == "deleted"
    assert long_memory.load_long_memory_records() == []


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_duplicate_detection_is_scoped_by_project(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    if backend == "jsonl":
        _use_jsonl(monkeypatch, repo_tmp_path)
    else:
        _use_sqlite(monkeypatch, repo_tmp_path)

    p1 = long_memory.save_long_memory("use pytest", source="tool", project="p1")
    assert p1["saved"] is True
    p2 = long_memory.save_long_memory("use pytest", source="tool", project="p2")
    assert p2["saved"] is True
    assert p2["memory_id"] != p1["memory_id"]

    again = long_memory.save_long_memory("use pytest", source="tool", project="p1")
    assert again["saved"] is False
    assert again["reason"] == "duplicate"
    assert again["memory_id"] == p1["memory_id"]
    assert len(long_memory.load_long_memory_records()) == 2


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_background_save_cannot_resurrect_forgotten_note(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    if backend == "jsonl":
        _use_jsonl(monkeypatch, repo_tmp_path)
    else:
        _use_sqlite(monkeypatch, repo_tmp_path)

    first = long_memory.save_long_memory("住所は京都市", source="tool")
    assert first["saved"] is True
    assert long_memory.delete_long_memory_by_id(first["memory_id"]) is True

    # A background re-learn from old logs must not bring the note back,
    # even under a fresh source_id.
    relearn = long_memory.save_long_memory(
        "住所は京都市", source="consolidation", source_id="consolidation:other"
    )
    assert relearn["saved"] is False
    assert relearn["reason"] == "deleted"
    assert long_memory.load_long_memory_records() == []

    # A fresh in-conversation save is new intent, not a re-learn.
    restated = long_memory.save_long_memory("住所は京都市", source="tool")
    assert restated["saved"] is True


def test_forgotten_note_keys_exclude_scoped_rows(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Scoped (Web) tombstones carry an owner_id; the local forget
    # boundary must only contain local tombstones.
    import time as _time

    from uagent.runtime.memory_store import open_memory_store
    from uagent.tools import long_memory

    _use_sqlite(monkeypatch, repo_tmp_path)
    saved = long_memory.save_long_memory("ローカルの忘却メモ", source="tool")
    assert saved["saved"] is True
    assert long_memory.delete_long_memory_by_id(saved["memory_id"]) is True

    store = open_memory_store(str(repo_tmp_path / "memory.sqlite3"))
    try:
        now = _time.time()
        store.db.execute(
            "INSERT INTO memories(memory_id, created_at, updated_at, note, "
            "owner, owner_id, project, audience_type, audience_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'personal', ?, 'deleted')",
            (
                "scopedtombstone1",
                now,
                now,
                "スコープ側の忘却メモ",
                "alice",
                "alice",
                "demo",
                "alice",
            ),
        )
        store.db.commit()
    finally:
        store.close()

    keys = long_memory.forgotten_note_keys()
    assert long_memory.note_key_for("ローカルの忘却メモ") in keys
    assert long_memory.note_key_for("スコープ側の忘却メモ") not in keys


def test_profile_items_matching_forgotten_notes_are_dropped(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.profile_manager import _drop_forgotten_profile_items
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    saved = long_memory.save_long_memory("テストは pytest を使う", source="tool")
    assert saved["saved"] is True
    assert long_memory.delete_long_memory_by_id(saved["memory_id"]) is True

    profile = _drop_forgotten_profile_items(
        {
            "preferences": ["テストは pytest を使う", "エディタは vim を使う"],
            "constraints": ["テストは pytest を使う"],
        }
    )
    assert profile["preferences"] == ["エディタは vim を使う"]
    assert profile["constraints"] == []


def test_marker_not_saved_for_non_local_web_turn(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Marker saves land in the legacy unscoped store (owner = the
    # server's OS login), so an authenticated non-local Web turn must
    # not trigger one; the local identity still saves as before.
    from uagent.runtime.identity_context import TurnContext, bind_turn_context
    from uagent.runtime.memory_marker import save_memory_marker
    from uagent.runtime.session_store import SessionStore
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    store = SessionStore(repo_tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="web")

    web_turn = TurnContext(
        principal_id="alice",
        room_id="room-1",
        project_id="demo",
        session_id=session.session_id,
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
        server_bound_project=True,
    )
    with bind_turn_context(web_turn):
        assert save_memory_marker("remember: リモートからのメモ") is None
        store.append_message(session.session_id, "user", "remember: リモートからのメモ")
    assert long_memory.load_long_memory_records() == []

    local_turn = TurnContext(
        principal_id="local",
        room_id="",
        project_id="demo",
        session_id=session.session_id,
        entry_point="web",
        authenticated=True,
        authn_kind="local",
    )
    with bind_turn_context(local_turn):
        store.append_message(session.session_id, "user", "remember: ローカルのメモ")
    records = long_memory.load_long_memory_records()
    assert [str(r.get("note")) for r in records] == ["ローカルのメモ"]
    store.close()


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_duplicate_detection_keeps_meaningful_punctuation(
    backend: str, repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools import long_memory

    if backend == "jsonl":
        _use_jsonl(monkeypatch, repo_tmp_path)
    else:
        _use_sqlite(monkeypatch, repo_tmp_path)

    first = long_memory.save_long_memory("Do not delete /tmp/a-b", source="tool")
    assert first["saved"] is True
    # Differing only in punctuation inside the text: a different note.
    second = long_memory.save_long_memory("Do not delete /tmp/ab", source="tool")
    assert second["saved"] is True
    assert second["memory_id"] != first["memory_id"]

    # Trailing sentence punctuation alone still counts as a duplicate.
    note = long_memory.save_long_memory("返事は日本語で", source="tool")
    assert note["saved"] is True
    dotted = long_memory.save_long_memory("返事は日本語で。", source="tool")
    assert dotted["saved"] is False
    assert dotted["reason"] == "duplicate"
    assert dotted["memory_id"] == note["memory_id"]
    assert len(long_memory.load_long_memory_records()) == 3


def test_legacy_jsonl_records_stay_editable_by_index(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    memory_file = repo_tmp_path / "mem.jsonl"
    memory_file.write_text(
        json.dumps({"ts": 1700000000.0, "note": "古いメモ1"})
        + "\n"
        + json.dumps({"ts": 1700000100.0, "note": "古いメモ2"})
        + "\n",
        encoding="utf-8",
    )

    assert long_memory.update_long_memory_entry(1, "書き換えたメモ2") is True
    records = long_memory.load_long_memory_records()
    assert [str(r.get("note")) for r in records] == ["古いメモ1", "書き換えたメモ2"]
    assert str(records[1].get("memory_id") or "").startswith("legacy-jsonl-")

    assert long_memory.delete_long_memory_entry(0) is True
    records = long_memory.load_long_memory_records()
    assert [str(r.get("note")) for r in records] == ["書き換えたメモ2"]
    deleted = long_memory.list_deleted_long_memory_records()
    assert [str(r.get("note")) for r in deleted] == ["古いメモ1"]

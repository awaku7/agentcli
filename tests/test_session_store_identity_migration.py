"""Session-scoped tool identity migration (schema version 1).

Tool-call and tool-result IDs come from providers and imported conversations,
so they are only unique inside one session. A store-wide primary key made a
second session that reused an ID fail with "belongs to another session" and
abort its LLM round.
"""

from __future__ import annotations

import sqlite3

import pytest

from uagent.runtime.session_store import SessionStore, SessionStoreError

_LEGACY_SCHEMA = """
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    project TEXT,
    project_key TEXT NOT NULL,
    project_path TEXT,
    entry_point TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    principal_id TEXT,
    room_id TEXT
);
CREATE TABLE tool_calls (
    call_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    result TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE tool_results (
    result_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    task_id TEXT,
    tool_name TEXT NOT NULL,
    result_class TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    summary TEXT NOT NULL,
    artifact_ref TEXT,
    importance TEXT NOT NULL,
    evictable INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    persistent_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_tool_calls_session_created ON tool_calls(session_id, created_at);
CREATE INDEX idx_tool_results_session_created ON tool_results(session_id, created_at);
"""

_SESSION_A = "a" * 32
_SESSION_B = "b" * 32


def _create_legacy_store(path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(_LEGACY_SCHEMA)
        for session_id in (_SESSION_A, _SESSION_B):
            connection.execute(
                "INSERT INTO sessions(session_id, project, project_key, entry_point) "
                "VALUES (?, 'demo', 'key', 'cli')",
                (session_id,),
            )
        connection.execute(
            "INSERT INTO tool_calls(call_id, session_id, tool_name, args_json, result, "
            "status) VALUES ('gemini_fc_1', ?, 'tool_catalog', '{}', 'first', 'success')",
            (_SESSION_A,),
        )
        connection.execute(
            "INSERT INTO tool_results(result_id, session_id, tool_name, result_class, "
            "size_bytes, summary, artifact_ref, importance, evictable, metadata_json, "
            "persistent_json, created_at) VALUES ('result_1', ?, 'tool_catalog', 'small', "
            "5, 'first', NULL, 'normal', 1, '{}', '{}', '2026-01-01T00:00:00+00:00')",
            (_SESSION_A,),
        )
        connection.commit()
    finally:
        connection.close()


def _primary_key_columns(store: SessionStore, table: str) -> dict[str, int]:
    return {
        str(row["name"]): int(row["pk"] or 0)
        for row in store._connection.execute(f"PRAGMA table_info({table})")
    }


def test_legacy_store_is_migrated_to_session_scoped_tool_identity(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    _create_legacy_store(path)

    store = SessionStore(path)
    try:
        assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        call_key = _primary_key_columns(store, "tool_calls")
        result_key = _primary_key_columns(store, "tool_results")
        assert call_key["session_id"] > 0 and call_key["call_id"] > 0
        assert result_key["session_id"] > 0 and result_key["result_id"] > 0

        calls = store.list_tool_calls(_SESSION_A)
        assert [call["call_id"] for call in calls] == ["gemini_fc_1"]
        assert calls[0]["result"] == "first"
        results = store.list_tool_results(_SESSION_A)
        assert [row["result_id"] for row in results] == ["result_1"]

        indexes = {
            str(row["name"])
            for row in store._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        assert {
            "idx_tool_calls_session_created",
            "idx_tool_results_session_created",
        } <= indexes
    finally:
        store.close()


def test_reused_tool_ids_are_recorded_for_both_sessions(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    _create_legacy_store(path)
    store = SessionStore(path)
    try:
        reused = store.record_tool_call(
            _SESSION_B,
            tool_name="tool_catalog",
            args={"query": "weather"},
            result="second",
            status="success",
            call_id="gemini_fc_1",
        )
        assert reused == "gemini_fc_1"
        store.record_tool_result(
            _SESSION_B,
            {
                "result_id": "result_1",
                "tool_name": "tool_catalog",
                "metadata": {},
            },
            "second",
        )

        assert len(store.list_tool_calls(_SESSION_A)) == 1
        second_calls = store.list_tool_calls(_SESSION_B)
        assert len(second_calls) == 1
        assert second_calls[0]["result"] == "second"
        assert len(store.list_tool_results(_SESSION_B)) == 1
    finally:
        store.close()


def test_duplicate_id_within_one_session_stays_idempotent(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    try:
        store.record_tool_call(
            session.session_id,
            tool_name="read_file",
            args={},
            result="ok",
            status="success",
            call_id="call-1",
        )
        store.record_tool_call(
            session.session_id,
            tool_name="read_file",
            args={},
            result="must not overwrite",
            status="failed",
            call_id="call-1",
        )
        assert store.list_tool_calls(session.session_id)[0]["result"] == "ok"
    finally:
        store.close()


def test_migration_is_idempotent_across_reopens(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    _create_legacy_store(path)

    first = SessionStore(path)
    first.close()
    second = SessionStore(path)
    try:
        assert second._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert len(second.list_tool_calls(_SESSION_A)) == 1
        assert len(second.list_tool_results(_SESSION_A)) == 1
    finally:
        second.close()


def test_failed_migration_leaves_the_legacy_store_intact(tmp_path, monkeypatch):
    path = tmp_path / "sessions.sqlite3"
    _create_legacy_store(path)

    def fail(*_args, **_kwargs):
        raise sqlite3.OperationalError("injected migration failure")

    monkeypatch.setattr(SessionStore, "_rebuild_identity_table", fail)
    with pytest.raises(SessionStoreError):
        SessionStore(path)
    monkeypatch.undo()

    connection = sqlite3.connect(path)
    try:
        table = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'tool_calls'"
        ).fetchone()[0]
        assert "call_id TEXT PRIMARY KEY" in table
        assert connection.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        connection.close()

    store = SessionStore(path)
    store.close()


def test_prune_does_not_delete_another_sessions_reused_result_id(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_a = store.create_session(project="demo", entry_point="cli")
    session_b = store.create_session(project="demo", entry_point="cli")
    try:
        store.record_tool_result(
            session_a.session_id,
            {
                "result_id": "dup",
                "tool_name": "tool",
                "metadata": {},
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            "oldest",
        )
        store.record_tool_result(
            session_a.session_id,
            {
                "result_id": "keep",
                "tool_name": "tool",
                "metadata": {},
                "created_at": "2026-01-02T00:00:00+00:00",
            },
            "newest",
        )
        store.record_tool_result(
            session_b.session_id,
            {
                "result_id": "dup",
                "tool_name": "tool",
                "metadata": {},
                "created_at": "2026-01-03T00:00:00+00:00",
            },
            "other session",
        )

        assert store.prune_tool_results(session_a.session_id, max_rows=1) == 1

        assert [
            row["result_id"] for row in store.list_tool_results(session_a.session_id)
        ] == ["keep"]
        assert [
            row["result_id"] for row in store.list_tool_results(session_b.session_id)
        ] == ["dup"]
    finally:
        store.close()


def test_fresh_store_is_created_at_the_current_schema_version(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    try:
        assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        call_key = _primary_key_columns(store, "tool_calls")
        assert call_key["session_id"] > 0 and call_key["call_id"] > 0
    finally:
        store.close()

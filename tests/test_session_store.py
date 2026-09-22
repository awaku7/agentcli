from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

import uagent.runtime.session_store as session_store_module

from uagent.runtime.session_store import (
    SessionStore,
    SessionStoreError,
    normalize_tool_call,
    project_id_from_path,
)


def test_env_opt_in_can_be_disabled_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_SESSION_STORE", "0")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(tmp_path / "ignored.sqlite3"))

    assert SessionStore.from_environment() is None


def test_env_opt_in_uses_configured_path(monkeypatch, tmp_path):
    db_path = tmp_path / "configured.sqlite3"
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(db_path))

    store = SessionStore.from_environment()
    assert store is not None
    session = store.create_session(project="demo", entry_point="cli")
    assert db_path.exists()
    assert store.get_session(session.session_id)["session_id"] == session.session_id


def test_legacy_default_store_is_moved_to_uag(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    legacy = SessionStore(tmp_path / ".uagent" / "sessions.sqlite3")
    session = legacy.create_session(project="legacy", entry_point="test")
    legacy.close()
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.delenv("UAGENT_SESSION_STORE_PATH", raising=False)

    store = SessionStore.from_environment()
    assert store is not None
    assert (tmp_path / ".uag" / "sessions.sqlite3").exists()
    assert not (tmp_path / ".uagent" / "sessions.sqlite3").exists()
    assert store.get_session(session.session_id)["project"] == "legacy"
    store.close()


def test_current_default_store_wins_and_legacy_is_removed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    legacy = SessionStore(tmp_path / ".uagent" / "sessions.sqlite3")
    legacy.close()
    current = SessionStore(tmp_path / ".uag" / "sessions.sqlite3")
    current.close()
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.delenv("UAGENT_SESSION_STORE_PATH", raising=False)

    store = SessionStore.from_environment()
    assert store is not None
    assert not (tmp_path / ".uagent" / "sessions.sqlite3").exists()
    assert (tmp_path / ".uag" / "sessions.sqlite3").exists()
    store.close()


def test_project_id_uses_workspace_directory_name():
    assert project_id_from_path(r"F:\KAIHATSU\agentcli") == "agentcli"
    assert project_id_from_path("/work/demo") == "demo"


def test_normalize_tool_call_supports_openai_and_flat_shapes():
    assert normalize_tool_call(
        {
            "id": "call-1",
            "function": {"name": "read_file", "arguments": '{"filename":"a"}'},
        }
    ) == ("call-1", "read_file", {"filename": "a"})
    assert normalize_tool_call(
        {"id": "call-2", "name": "search", "arguments": {"q": "x"}}
    ) == ("call-2", "search", {"q": "x"})


def test_same_project_name_keeps_distinct_project_keys(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    first = store.create_session(
        project="agentcli", project_path=r"F:\A\agentcli", entry_point="cli"
    )
    second = store.create_session(
        project="agentcli", project_path=r"F:\B\agentcli", entry_point="cli"
    )

    assert first.project_key != second.project_key
    assert store.get_session(first.session_id)["project_path"] == r"F:\A\agentcli"


def test_create_session_has_unique_id_and_can_be_reopened(tmp_path):
    db_path = tmp_path / "sessions.sqlite3"
    store = SessionStore(db_path)

    first = store.create_session(project="demo", entry_point="cli")
    second = store.create_session(project="demo", entry_point="web")

    assert first.session_id != second.session_id
    assert store.get_session(first.session_id)["project"] == "demo"

    reopened = SessionStore(db_path)
    assert reopened.get_session(first.session_id)["entry_point"] == "cli"


def test_touch_session_preserves_created_at_and_updates_last_used_at(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    original_created = "2001-02-03 04:05:06"
    original_last_used = "2001-02-03 04:05:06"
    store._execute(
        "UPDATE sessions SET created_at = ?, last_used_at = ? WHERE session_id = ?",
        (original_created, original_last_used, session.session_id),
    )

    store.touch_session(session.session_id)

    row = store.get_session(session.session_id)
    assert row["created_at"] == original_created
    assert row["last_used_at"] != original_last_used


def test_list_sessions_orders_by_last_used_at(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    first = store.create_session(project="demo", entry_point="cli")
    second = store.create_session(project="demo", entry_point="cli")
    store._execute(
        "UPDATE sessions SET created_at = ?, last_used_at = ? WHERE session_id = ?",
        ("2026-09-22 10:00:00", "2026-09-22 10:00:00", first.session_id),
    )
    store._execute(
        "UPDATE sessions SET created_at = ?, last_used_at = ? WHERE session_id = ?",
        ("2026-09-21 10:00:00", "2026-09-22 11:00:00", second.session_id),
    )

    rows = store.list_sessions()

    assert [row["session_id"] for row in rows[:2]] == [
        second.session_id,
        first.session_id,
    ]
    assert rows[0]["created_at"] == "2026-09-21 10:00:00"
    assert rows[0]["last_used_at"] == "2026-09-22 11:00:00"


def test_legacy_session_schema_recovers_created_at_and_preserves_last_used(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            project_key TEXT NOT NULL,
            project_path TEXT,
            entry_point TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute("""
        CREATE TABLE messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute(
        "INSERT INTO sessions(session_id, project, project_key, entry_point, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("legacy-1", "demo", "legacy-key", "cli", "2026-09-22 12:00:00"),
    )
    connection.execute(
        "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        ("legacy-1", "user", "yesterday work", "2026-09-21 09:00:00"),
    )
    connection.commit()
    connection.close()

    store = SessionStore(db_path)

    row = store.get_session("legacy-1")
    assert row["created_at"] == "2026-09-21 09:00:00"
    assert row["last_used_at"] == "2026-09-22 12:00:00"


def test_legacy_session_schema_does_not_move_creation_forward(tmp_path):
    db_path = tmp_path / "legacy-untouched.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            project_key TEXT NOT NULL,
            project_path TEXT,
            entry_point TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute("""
        CREATE TABLE messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute(
        "INSERT INTO sessions(session_id, project, project_key, entry_point, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("legacy-2", "demo", "legacy-key", "cli", "2026-09-21 08:59:00"),
    )
    connection.execute(
        "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        ("legacy-2", "user", "first message", "2026-09-21 09:00:00"),
    )
    connection.commit()
    connection.close()

    store = SessionStore(db_path)

    row = store.get_session("legacy-2")
    assert row["created_at"] == "2026-09-21 08:59:00"
    assert row["last_used_at"] == "2026-09-21 08:59:00"


def test_execute_retries_transient_database_lock(monkeypatch, tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    calls = 0

    def execute(_sql, _parameters):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    store._connection = SimpleNamespace(execute=execute)
    delays = []
    monkeypatch.setattr(session_store_module.time, "sleep", delays.append)

    assert store._execute("SELECT 1") == "ok"
    assert calls == 3
    assert delays == [0.25, 0.5]


def test_sqlite_runtime_pragmas_and_indexes_are_configured(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")

    assert store._connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert store._connection.execute("PRAGMA synchronous").fetchone()[0] == 1
    assert store._connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert store._connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    indexes = {
        row["name"]
        for row in store._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    assert {
        "idx_sessions_last_used",
        "idx_sessions_project_last_used",
        "idx_messages_session_role_id",
        "idx_tool_calls_session_created",
        "idx_policy_decisions_session_id",
        "idx_context_decisions_session_id",
    } <= indexes


def test_replace_messages_is_atomic_on_mid_batch_failure(tmp_path, monkeypatch):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    store.append_message(session.session_id, "user", "original")

    original = store._append_message_unlocked
    calls = 0

    def fail_on_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected replace failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "_append_message_unlocked", fail_on_second)
    with pytest.raises(RuntimeError, match="injected replace failure"):
        store.replace_messages(
            session.session_id,
            [
                {"role": "user", "content": "new-one"},
                {"role": "assistant", "content": "new-two"},
            ],
        )

    assert store.list_messages(session.session_id) == [
        {"role": "user", "content": "original"}
    ]
    assert store.search("original")
    assert store.search("new-one") == []


def test_messages_are_returned_in_sequence(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")

    store.append_message(session.session_id, "user", "hello")
    store.append_message(session.session_id, "assistant", "world")

    messages = store.list_messages(session.session_id)
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert [message["content"] for message in messages] == ["hello", "world"]


def test_tool_call_can_be_recorded_and_duplicate_id_is_idempotent(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")

    first = store.record_tool_call(
        session.session_id,
        tool_name="read_file",
        args={"filename": "README.md"},
        result="ok",
        status="success",
        call_id="call-1",
    )
    second = store.record_tool_call(
        session.session_id,
        tool_name="read_file",
        args={"filename": "README.md"},
        result="changed result must not overwrite",
        status="failed",
        call_id="call-1",
    )

    assert first == second
    assert store.list_tool_calls(session.session_id)[0]["result"] == "ok"


def test_search_finds_messages_and_filters_by_project(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    alpha = store.create_session(project="alpha", entry_point="cli")
    beta = store.create_session(project="beta", entry_point="cli")
    store.append_message(alpha.session_id, "user", "SQLite session search")
    store.append_message(beta.session_id, "user", "unrelated project")

    results = store.search("SQLite")
    assert [row["session_id"] for row in results] == [alpha.session_id]

    assert store.search("project", project="alpha") == []


def test_sensitive_values_are_redacted_before_storage(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")

    store.append_message(
        session.session_id,
        "user",
        "token=sk-secret-value password=hunter2 Cookie: session-cookie",
    )

    content = store.list_messages(session.session_id)[0]["content"]
    assert "sk-secret-value" not in content
    assert "hunter2" not in content
    assert "session-cookie" not in content
    assert "[REDACTED]" in content


def test_tool_call_arguments_are_redacted_before_storage(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")

    store.record_tool_call(
        session.session_id,
        tool_name="http_request",
        args={
            "headers": {"Authorization": "Bearer secret-token"},
            "password": "hunter2",
            "nested": [{"api_key": "sk-secret-value"}],
        },
        result="ok",
        status="success",
    )

    args = store.list_tool_calls(session.session_id)[0]["args"]
    assert "secret-token" not in str(args)
    assert "hunter2" not in str(args)
    assert "sk-secret-value" not in str(args)
    assert "********" in str(args)


def test_policy_decisions_can_be_recorded_without_secrets(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")

    store.record_policy_decision(
        session.session_id,
        tool_name="http_request",
        decision="deny",
        args={"token": "secret-token"},
        reason="configured policy",
        tool_call_id="call-1",
    )

    rows = store.list_policy_decisions(session.session_id)
    assert rows[0]["decision"] == "deny"
    assert rows[0]["reason"] == "configured policy"
    assert "secret-token" not in str(rows[0]["args"])


def test_context_decisions_can_be_persisted_and_listed_without_secrets(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")

    count = store.record_context_decisions(
        session.session_id,
        [
            {
                "item_id": "result-1",
                "source": "tool_result",
                "section": "tool_results",
                "action": "COMPACT",
                "reason": "contains token=secret-value",
                "importance": 0.75,
                "original_chars": 100,
                "projected_chars": 40,
                "reference": "artifact://result-1",
            }
        ],
    )

    assert count == 1
    row = store.list_context_decisions(session.session_id)[0]
    assert row["item_id"] == "result-1"
    assert row["action"] == "COMPACT"
    assert row["importance"] == 0.75
    assert row["original_chars"] == 100
    assert "secret-value" not in str(row)


def test_unknown_session_and_invalid_tool_status_raise(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")

    with pytest.raises(SessionStoreError):
        store.append_message("missing", "user", "text")

    session = store.create_session(project="demo", entry_point="cli")
    with pytest.raises(ValueError):
        store.record_tool_call(
            session.session_id,
            tool_name="x",
            args={},
            result="",
            status="unknown",
        )


def test_busy_database_is_reported_as_store_error(tmp_path):
    db_path = tmp_path / "sessions.sqlite3"
    store = SessionStore(db_path)
    lock = sqlite3.connect(db_path)
    lock.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(SessionStoreError):
            store.create_session(project="demo", entry_point="cli")
    finally:
        lock.rollback()
        lock.close()


def test_delete_session_removes_messages_and_search_rows(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    store.append_message(session.session_id, "user", "removable text")

    store.delete_session(session.session_id)

    assert store.list_sessions() == []
    assert store.search("removable") == []
    with pytest.raises(SessionStoreError):
        store.get_session(session.session_id)


def test_vacuum_reclaims_deleted_session_pages(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    store.append_message(session.session_id, "user", "x" * 10000)
    store.delete_session(session.session_id)
    store.vacuum()


def test_import_jsonl_is_idempotent_and_preserves_payload(tmp_path):
    source = tmp_path / "scheck_log_old.jsonl"
    source.write_text(
        json.dumps(
            {"role": "assistant", "content": "answer", "response_id": "resp_1"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    store = SessionStore(tmp_path / "sessions.sqlite3")

    first = store.import_jsonl(source, project="demo")
    second = store.import_jsonl(source, project="other")

    assert first.session_id == second.session_id
    assert store.list_sessions() and len(store.list_sessions()) == 1
    assert store.list_messages(first.session_id)[0]["response_id"] == "resp_1"

from __future__ import annotations

import sqlite3

import pytest

from uagent.runtime.session_store import (
    SessionStore,
    SessionStoreError,
    normalize_tool_call,
    project_id_from_path,
)


def test_env_opt_in_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("UAGENT_SESSION_STORE", raising=False)
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

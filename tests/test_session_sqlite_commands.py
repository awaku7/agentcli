from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.session_store import (
    SessionStore,
    attach_opt_in_session_store,
    detach_opt_in_session_store,
)
from uagent.util_cmd_files import _handle_cmd_logs
from uagent.util_cmd_session import _handle_cmd_load


def test_logs_and_load_use_sqlite_backend(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    old = db.create_session(project="old", entry_point="cli")
    db.append_message(old.session_id, "user", "old question")
    db.append_message(old.session_id, "assistant", "old answer")
    db.save_session_summary(old.session_id, "Summary should be visible")
    current = db.create_session(project="current", entry_point="cli")
    core = SimpleNamespace(session_store=db, session_id=current.session_id)
    messages: list[dict] = []

    assert _handle_cmd_logs("all", core=core, tr=lambda text, **_: text)
    output = capsys.readouterr().out
    assert old.session_id in output
    assert "summary: Summary should be visible" in output
    assert "first: old question" not in output
    assert "last:  old answer" not in output

    assert _handle_cmd_load(
        old.session_id, messages, core=core, tr=lambda text, **_: text
    )
    assert [message["content"] for message in messages] == [
        "old question",
        "old answer",
    ]
    db.close()


def test_load_switches_sqlite_persistence_target(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(tmp_path / "sessions.sqlite3"))
    logged: list[dict] = []
    core = SimpleNamespace(log_message=logged.append)
    store, current_id = attach_opt_in_session_store(
        core, project_path=tmp_path, entry_point="cli"
    )
    assert store is not None
    old = store.create_session(project="old", entry_point="cli")
    store.append_message(old.session_id, "user", "old question")
    messages: list[dict] = []

    assert _handle_cmd_load(
        old.session_id, messages, core=core, tr=lambda text, **_: text
    )
    assert core.session_id == old.session_id
    core.log_message({"role": "user", "content": "follow-up"})

    old_contents = [m["content"] for m in store.list_messages(old.session_id)]
    current_contents = [m["content"] for m in store.list_messages(current_id)]
    assert old_contents == ["old question", "follow-up"]
    assert current_contents == []
    detach_opt_in_session_store(core)


def test_sqlite_clean_preserves_active_session(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    old = db.create_session(project="old", entry_point="cli")
    db.append_message(old.session_id, "user", "short")
    current = db.create_session(project="current", entry_point="cli")
    core = SimpleNamespace(session_store=db, session_id=current.session_id)

    # Decline the destructive confirmation.
    monkeypatch.setattr(
        "uagent.tools.human_ask_tool.run_tool",
        lambda args: {"user_reply": "c"},
    )
    from uagent.util_cmd_session import _handle_cmd_clean

    assert _handle_cmd_clean("", core=core, tr=lambda text, **_: text)
    assert "Cancelled" in capsys.readouterr().out
    assert db.get_session(old.session_id)["session_id"] == old.session_id
    assert db.get_session(current.session_id)["session_id"] == current.session_id
    db.close()

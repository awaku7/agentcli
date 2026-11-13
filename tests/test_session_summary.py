from __future__ import annotations

import time

from uagent.runtime.session_store import SessionStore


def test_session_summary_is_persisted_and_reopened(tmp_path):
    db_path = tmp_path / "sessions.sqlite3"
    store = SessionStore(db_path)
    session = store.create_session(project="agentcli", entry_point="cli")
    store.save_session_summary(session.session_id, "Implemented session search.")

    reopened = SessionStore(db_path)
    assert (
        reopened.get_session_summary(session.session_id)
        == "Implemented session search."
    )


def test_marked_messages_are_saved_immediately(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp_path / "mem.jsonl"))
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="agentcli", entry_point="cli")
    store.append_message(session.session_id, "user", "remember: use pytest first")
    store.append_message(session.session_id, "user", "ordinary request")

    from uagent.tools.long_memory import load_long_memory_records

    notes = [str(r.get("note")) for r in load_long_memory_records()]
    assert notes == ["use pytest first"]
    notices = store.drain_memory_notices()
    assert len(notices) == 1
    assert "use pytest first" in notices[0]
    store.close()


def test_summary_is_stale_only_when_messages_follow_the_summary(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="agentcli", entry_point="cli")
    store.append_message(session.session_id, "user", "first question")
    store.append_message(session.session_id, "assistant", "first answer")
    store.save_session_summary(session.session_id, "Implemented session search.")

    # The summary was created after the last message: not stale.
    assert store.summary_is_stale(session.session_id) is False

    # Conversation continues after the summary was created: stale.  A short
    # sleep guarantees the follow-up message lands in a later second than
    # the summary (SQLite CURRENT_TIMESTAMP has second resolution).
    time.sleep(1.1)
    store.append_message(session.session_id, "user", "follow-up")
    assert store.summary_is_stale(session.session_id) is True

    # Re-summarizing after the new messages makes the summary current again.
    store.save_session_summary(session.session_id, "Updated summary.")
    assert store.summary_is_stale(session.session_id) is False
    store.close()

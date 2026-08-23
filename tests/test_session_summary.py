from __future__ import annotations

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


def test_memory_candidates_require_explicit_marker_and_are_not_saved(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="agentcli", entry_point="cli")
    store.append_message(session.session_id, "user", "remember: use pytest first")
    store.append_message(session.session_id, "user", "ordinary request")

    candidates = store.list_memory_candidates(session.session_id)
    assert candidates == ["use pytest first"]
    # Candidate extraction is read-only; it does not write long-term memory.

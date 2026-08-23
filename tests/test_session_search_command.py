from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.session_store import SessionStore
from uagent.util_cmd_session import _handle_cmd_sessions


def test_sessions_search_prints_matching_rows(tmp_path, monkeypatch, capsys):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    store.append_message(session.session_id, "user", "find this durable note")
    core = SimpleNamespace(session_store=store)

    assert _handle_cmd_sessions("search durable", core=core, tr=lambda text, **_: text)
    output = capsys.readouterr().out
    assert session.session_id in output
    assert "find this durable note" in output


def test_sessions_candidates_can_be_approved(tmp_path, capsys, monkeypatch):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    store.append_message(session.session_id, "user", "remember: use pytest first")
    core = SimpleNamespace(session_store=store, session_id=session.session_id)

    monkeypatch.setattr(
        "uagent.util_cmd_session.personal_long_memory.append_long_memory",
        lambda note: None,
    )
    assert _handle_cmd_sessions("candidates", core=core, tr=lambda text, **_: text)
    assert "use pytest first" in capsys.readouterr().out
    assert _handle_cmd_sessions("approve 1", core=core, tr=lambda text, **_: text)
    assert "approved" in capsys.readouterr().out.lower()


def test_sessions_search_is_unavailable_without_opt_in(capsys):
    core = SimpleNamespace(session_store=None)

    assert _handle_cmd_sessions("search anything", core=core, tr=lambda text, **_: text)
    assert "not enabled" in capsys.readouterr().out.lower()

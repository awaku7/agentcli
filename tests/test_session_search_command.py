from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.session_store import SessionStore
from uagent.i18n import set_thread_lang
from uagent.util_cmd_session import _handle_cmd_load, _handle_cmd_sessions


def test_sessions_search_prints_matching_rows(tmp_path, monkeypatch, capsys):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    store.append_message(session.session_id, "user", "find this durable note")
    core = SimpleNamespace(session_store=store)

    assert _handle_cmd_sessions("search durable", core=core, tr=lambda text, **_: text)
    output = capsys.readouterr().out
    assert session.session_id in output
    assert "find this durable note" in output


def test_sessions_search_prints_one_row_per_session(tmp_path, capsys):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session = store.create_session(project="demo", entry_point="cli")
    store.append_message(session.session_id, "user", "durable first hit")
    store.append_message(session.session_id, "assistant", "durable second hit")
    other = store.create_session(project="demo", entry_point="cli")
    store.append_message(other.session_id, "user", "durable other hit")
    core = SimpleNamespace(session_store=store)

    assert _handle_cmd_sessions("search durable", core=core, tr=lambda text, **_: text)
    lines = capsys.readouterr().out.splitlines()
    # Shared list view: header + summary/first/last + hit + id per session.
    result_blocks = [line for line in lines if line[:1] == "[" and line[1:2].isdigit()]
    assert len(result_blocks) == 2
    output = chr(10).join(lines)
    assert output.count(session.session_id) == 1
    assert output.count(other.session_id) == 1
    assert "summary: -" in output
    assert "hit: user: durable first hit" in output
    assert "hit: user: durable other hit" in output

    messages = []
    assert _handle_cmd_load("0", messages, core=core, tr=lambda text, **_: text)
    assert messages[0]["content"] == "durable first hit"


def test_sessions_candidates_can_be_approved(tmp_path, capsys, monkeypatch):
    # Pin the gettext locale so the assertion is independent of the host.
    monkeypatch.setenv("UAGENT_LANG", "en")
    set_thread_lang("en")
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


def test_sessions_load_matches_load_output_shape(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("UAGENT_LANG", "en")
    set_thread_lang("en")
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    store = SessionStore(tmp_path / "sessions.sqlite3")
    old = store.create_session(project="demo", entry_point="cli")
    store.append_message(old.session_id, "user", "old question")
    store.append_message(old.session_id, "assistant", "old answer")
    store.save_session_summary(old.session_id, "demo summary")
    current = store.create_session(project="demo", entry_point="cli")

    load_messages: list[dict] = []
    load_core = SimpleNamespace(session_store=store, session_id=current.session_id)
    assert _handle_cmd_load(
        old.session_id, load_messages, core=load_core, tr=lambda text, **_: text
    )
    load_output = capsys.readouterr().out

    sessions_messages: list[dict] = []
    sessions_core = SimpleNamespace(session_store=store, session_id=current.session_id)
    assert _handle_cmd_sessions(
        f"load {old.session_id}",
        messages_ref=sessions_messages,
        core=sessions_core,
        tr=lambda text, **_: text,
    )
    sessions_output = capsys.readouterr().out

    assert [m.get("content") for m in load_messages] == [
        m.get("content") for m in sessions_messages
    ]
    for marker in ("created:", "project:", "messages:", "first:", "last:"):
        assert marker in load_output
        assert marker in sessions_output
    # Loaded detail must show real values, not "-" fallbacks.
    assert "summary: demo summary" in load_output
    assert "summary: demo summary" in sessions_output
    assert "first: old question" in load_output
    assert "first: old question" in sessions_output
    # Same detail layout, only the command tag differs.
    assert sessions_output.replace("[sessions]", "[load]") == load_output.replace(
        "SQLite session loaded", "Session loaded"
    ).replace("Conversation loaded", "Conversation loaded")


def test_sessions_search_is_unavailable_without_opt_in(capsys, monkeypatch):
    # Pin the gettext locale so the assertion is independent of the host.
    monkeypatch.setenv("UAGENT_LANG", "en")
    set_thread_lang("en")
    core = SimpleNamespace(session_store=None)

    assert _handle_cmd_sessions("search anything", core=core, tr=lambda text, **_: text)
    assert "not enabled" in capsys.readouterr().out.lower()

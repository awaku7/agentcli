from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from uagent.runtime.session_store import (
    SessionStore,
    attach_opt_in_session_store,
    detach_opt_in_session_store,
)
from uagent.util_cmd_files import _handle_cmd_logs
from uagent.util_cmd_session import _handle_cmd_load
from uagent.util_cmd_session import _handle_cmd_sessions
from uagent.util_cmd_session import bind_session_selection_context


@pytest.mark.parametrize("loader", [":load 0", ":sessions load 0"])
def test_logs_replaces_previous_session_selection(loader, monkeypatch, tmp_path):
    from uagent.util_tools import handle_command

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    try:
        old = db.create_session(project="old", entry_point="cli")
        db.append_message(old.session_id, "user", "old")
        active = db.create_session(project="active", entry_point="cli")
        core = SimpleNamespace(session_store=db, session_id=active.session_id)
        messages = []
        assert handle_command(":sessions list", messages, None, "", core=core)
        core._session_search_results = {0: active.session_id}
        assert handle_command(":logs all", messages, None, "", core=core)
        assert core._session_search_results == {0: old.session_id}
        assert handle_command(loader, messages, None, "", core=core)
        assert [message["content"] for message in messages] == ["old"]
    finally:
        db.close()


@pytest.mark.parametrize("loader", [":load 1", ":sessions load 1"])
def test_empty_search_preserves_last_numbered_list(loader, monkeypatch, tmp_path):
    from uagent.util_tools import handle_command

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    try:
        rows = []
        for label in ("active", "wanted", "other"):
            session = db.create_session(project=label, entry_point="cli")
            db.append_message(session.session_id, "user", label)
            rows.append({"session_id": session.session_id})
        monkeypatch.setattr(db, "list_sessions", lambda: rows)
        core = SimpleNamespace(session_store=db, session_id=rows[0]["session_id"])
        messages = []
        assert handle_command(":sessions list", messages, None, "", core=core)
        assert handle_command(
            ":sessions search no-such-fact", messages, None, "", core=core
        )
        assert handle_command(loader, messages, None, "", core=core)
        assert [message["content"] for message in messages] == ["wanted"]
    finally:
        db.close()


def test_room_session_views_are_isolated_on_shared_core(monkeypatch, tmp_path):
    from uagent.util_tools import handle_command

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    try:
        first = db.create_session(project="first", entry_point="cli")
        second = db.create_session(project="second", entry_point="cli")
        db.append_message(first.session_id, "user", "first-room-fact")
        db.append_message(second.session_id, "user", "second-room-fact")
        core = SimpleNamespace(
            session_store=db,
            session_id=None,
            _session_search_results={0: "cli-selection"},
        )
        first_room = SimpleNamespace(history=[])
        second_room = SimpleNamespace(history=[])
        with bind_session_selection_context(first_room):
            assert handle_command(
                ":sessions search first-room-fact",
                first_room.history,
                None,
                "",
                core=core,
            )
        with bind_session_selection_context(second_room):
            assert handle_command(
                ":sessions search second-room-fact",
                second_room.history,
                None,
                "",
                core=core,
            )
        with bind_session_selection_context(first_room):
            assert handle_command(":load 0", first_room.history, None, "", core=core)
        with bind_session_selection_context(second_room):
            assert handle_command(
                ":sessions load 0", second_room.history, None, "", core=core
            )
        assert [message["content"] for message in first_room.history] == [
            "first-room-fact"
        ]
        assert [message["content"] for message in second_room.history] == [
            "second-room-fact"
        ]
        assert core._session_search_results == {0: "cli-selection"}
    finally:
        db.close()


@pytest.mark.parametrize("view", ["list", "list --verbose", "load", ":load"])
@pytest.mark.parametrize("loader", ["load", ":load"])
def test_load_index_uses_last_displayed_session_view(
    view, loader, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    try:
        rows = []
        for label in ("active", "wanted", "other"):
            session = db.create_session(project=label, entry_point="cli")
            db.append_message(session.session_id, "user", label)
            rows.append({"session_id": session.session_id, "project": label})
        monkeypatch.setattr(db, "list_sessions", lambda: rows)
        core = SimpleNamespace(
            session_store=db,
            session_id=rows[0]["session_id"],
            _session_search_results={
                0: rows[2]["session_id"],
                1: rows[2]["session_id"],
            },
        )
        if view == ":load":
            assert _handle_cmd_load("", [], core=core, tr=lambda text, **_: text)
        else:
            assert _handle_cmd_sessions(
                view, messages_ref=[], core=core, tr=lambda text, **_: text
            )
        output = capsys.readouterr().out
        index = 1 if view.startswith("list") else 0
        assert f"[{index}]" in output
        assert rows[1]["session_id"] in output
        # The displayed numbering must survive changes to the store's order.
        rows.reverse()
        messages = []
        if loader == ":load":
            assert _handle_cmd_load(
                str(index), messages, core=core, tr=lambda text, **_: text
            )
        else:
            assert _handle_cmd_sessions(
                f"load {index}",
                messages_ref=messages,
                core=core,
                tr=lambda text, **_: text,
            )
        assert [message["content"] for message in messages] == ["wanted"]
    finally:
        db.close()


def test_sessions_list_active_index_does_not_load_another_session(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    try:
        active = db.create_session(project="active", entry_point="cli")
        other = db.create_session(project="other", entry_point="cli")
        db.append_message(other.session_id, "user", "other")
        monkeypatch.setattr(
            db,
            "list_sessions",
            lambda: [
                {"session_id": active.session_id},
                {"session_id": other.session_id},
            ],
        )
        core = SimpleNamespace(session_store=db, session_id=active.session_id)
        messages = [{"role": "user", "content": "keep active"}]
        assert _handle_cmd_sessions("list", core=core, tr=lambda text, **_: text)
        assert _handle_cmd_sessions(
            "load 0", messages_ref=messages, core=core, tr=lambda text, **_: text
        )
        assert messages == [{"role": "user", "content": "keep active"}]
        assert core.session_id == active.session_id
    finally:
        db.close()


def test_cont_ignores_displayed_indices_and_loads_newest_inactive(
    monkeypatch, tmp_path, capsys
):
    from uagent.util_tools import handle_command

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    try:
        active = db.create_session(project="active", entry_point="cli")
        wanted = db.create_session(project="wanted", entry_point="cli")
        other = db.create_session(project="other", entry_point="cli")
        db.append_message(active.session_id, "user", "current")
        db.append_message(wanted.session_id, "user", "wanted")
        db.append_message(other.session_id, "user", "other")
        # Displayed list includes active at [0]; :cont must still load wanted.
        rows = [
            {"session_id": active.session_id},
            {"session_id": wanted.session_id},
            {"session_id": other.session_id},
        ]
        monkeypatch.setattr(db, "list_sessions", lambda: rows)
        core = SimpleNamespace(session_store=db, session_id=active.session_id)
        messages = [{"role": "user", "content": "current"}]
        assert _handle_cmd_sessions("list", core=core, tr=lambda text, **_: text)
        assert core._session_search_results[0] == active.session_id
        # Explicit :load 0 must not reload the active session.
        assert _handle_cmd_load("0", messages, core=core, tr=lambda text, **_: text)
        assert messages == [{"role": "user", "content": "current"}]
        assert "already active" in capsys.readouterr().out.lower()
        # :cont deliberately chooses the newest inactive session instead.
        assert handle_command(":cont", messages, None, "", core=core)
        assert [message["content"] for message in messages] == ["wanted"]
    finally:
        db.close()


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
    assert "first: old question" in output
    # list_sessions() tracks user turns, so last is the latest user message.
    assert "last:  old question" in output

    assert _handle_cmd_load(
        old.session_id, messages, core=core, tr=lambda text, **_: text
    )
    assert [message["content"] for message in messages] == [
        "old question",
        "old answer",
    ]
    db.close()


def test_sessions_list_is_compact_by_default(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    session = db.create_session(project="demo", entry_point="cli")
    db.append_message(session.session_id, "user", "a question")
    db.save_session_summary(session.session_id, "a useful summary")
    core = SimpleNamespace(session_store=db, session_id=None)

    assert _handle_cmd_sessions("list", core=core, tr=lambda text, **_: text)
    compact = capsys.readouterr().out
    assert session.session_id in compact
    assert "a useful summary" in compact
    assert "summary:" not in compact
    assert compact.count("\n") == 1

    assert _handle_cmd_sessions("list --verbose", core=core, tr=lambda text, **_: text)
    verbose = capsys.readouterr().out
    assert "summary: a useful summary" in verbose
    assert "first: a question" in verbose
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


def test_load_restores_sqlite_session_workdir(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    target_dir = tmp_path / "session-workdir"
    target_dir.mkdir()
    old = db.create_session(project="old", entry_point="cli", project_path=target_dir)
    db.append_message(old.session_id, "user", "old question")
    core = SimpleNamespace(
        session_store=db, session_id=None, log_message=lambda _: None
    )
    messages: list[dict] = []
    previous = os.getcwd()
    try:
        assert _handle_cmd_load(
            old.session_id, messages, core=core, tr=lambda text, **_: text
        )
        assert os.path.normcase(os.getcwd()) == os.path.normcase(str(target_dir))
        assert any(
            str(message.get("content", "")).startswith("[CWD]") for message in messages
        )
    finally:
        os.chdir(previous)
        db.close()


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


def test_sessions_summarize_replaces_stale_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    session = db.create_session(project="agentcli", entry_point="cli")
    db.append_message(session.session_id, "user", "first question")
    db.append_message(session.session_id, "assistant", "first answer")
    db.save_session_summary(session.session_id, "Fresh summary.")

    core = SimpleNamespace(session_store=db, session_id=session.session_id)
    compress_calls: list[str] = []

    def fake_compress(client, depname, messages, keep_last=1, emit_log=True):
        compress_calls.append("called")
        return [
            {
                "role": "system",
                "content": "Summary of the conversation so far:\nUpdated summary",
            }
        ]

    core.compress_history_with_llm = fake_compress
    from uagent.util_cmd_session import _handle_cmd_sessions

    def run_summarize() -> None:
        assert _handle_cmd_sessions(
            f"summarize {session.session_id}",
            messages_ref=[],
            client=object(),
            depname="test-model",
            core=core,
            tr=lambda text, **_: text,
        )

    # A summary that is still current is skipped without an LLM call.
    run_summarize()
    assert compress_calls == []
    assert db.get_session_summary(session.session_id) == "Fresh summary."

    # A conversation continued after the summary makes it stale: re-summarize
    # (this is the :load + more turns + :exit shutdown path).
    db.append_message(session.session_id, "user", "follow-up")
    db._execute(
        "UPDATE messages SET created_at = datetime('now', '+1 minute') "
        "WHERE session_id = ? AND message_id = "
        "(SELECT MAX(message_id) FROM messages WHERE session_id = ?)",
        (session.session_id, session.session_id),
    )
    run_summarize()
    assert compress_calls == ["called"]
    assert db.get_session_summary(session.session_id) == "Updated summary"
    db.close()


def test_sessions_summarize_only_processes_first_ten_records(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    for index in range(12):
        session = db.create_session(project=f"project-{index}", entry_point="cli")
        db.append_message(session.session_id, "user", f"question-{index}")
        db.append_message(session.session_id, "assistant", f"answer-{index}")

    expected = [
        db.list_messages(row["session_id"])[0]["content"]
        for row in db.list_sessions()[:10]
    ]
    summarized: list[str] = []
    core = SimpleNamespace(session_store=db, session_id=None)

    def fake_compress(client, depname, messages, keep_last=1, emit_log=True):
        summarized.append(messages[0]["content"])
        return [
            {
                "role": "system",
                "content": "Summary of the conversation so far:" + chr(10) + "Summary",
            }
        ]

    core.compress_history_with_llm = fake_compress
    assert _handle_cmd_sessions(
        "summarize",
        messages_ref=[],
        client=object(),
        depname="test-model",
        core=core,
        tr=lambda text, **_: text,
    )

    assert len(summarized) == 10
    assert sorted(summarized) == sorted(expected)
    assert "[10/10]" in capsys.readouterr().out
    db.close()


def test_sessions_summarize_aborts_cleanly_on_keyboard_interrupt(
    monkeypatch, tmp_path, capsys
):
    """Ctrl+C during a summarize LLM call must not raise a raw traceback."""
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    session = db.create_session(project="agentcli", entry_point="cli")
    db.append_message(session.session_id, "user", "first question")
    db.append_message(session.session_id, "assistant", "first answer")

    core = SimpleNamespace(session_store=db, session_id=session.session_id)

    def raising_compress(client, depname, messages, keep_last=1, emit_log=True):
        raise KeyboardInterrupt

    core.compress_history_with_llm = raising_compress

    # Should return normally (aborting the remaining sessions) instead of
    # propagating the KeyboardInterrupt up to the CLI shutdown path.
    assert _handle_cmd_sessions(
        f"summarize {session.session_id}",
        messages_ref=[],
        client=object(),
        depname="test-model",
        core=core,
        tr=lambda text, **_: text,
    )
    out = capsys.readouterr().out
    # The message is translated per active locale; "Ctrl+C" and the session
    # id are locale-independent markers of the interrupted path.
    assert "Ctrl+C" in out
    assert session.session_id in out
    # The interrupted session must not have a summary stored.
    assert db.get_session_summary(session.session_id) is None
    db.close()


def test_load_imported_sqlite_session_restores_system_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    session = db.create_session(project="imported", entry_point="jsonl-import")
    db.append_message(session.session_id, "user", "old question")
    core = SimpleNamespace(
        session_store=db,
        session_id="current",
        SYSTEM_PROMPT="current system prompt",
    )
    messages: list[dict] = []

    assert _handle_cmd_load(
        session.session_id, messages, core=core, tr=lambda text, **_: text
    )
    assert messages[0] == {"role": "system", "content": "current system prompt"}
    assert messages[1] == {"role": "user", "content": "old question"}
    db.close()


def test_sessions_search_matches_tool_payload_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    db = SessionStore(tmp_path / "sessions.sqlite3")
    session = db.create_session(project="agentcli", entry_point="cli")
    db.append_message(
        session.session_id,
        "tool",
        "command completed",
        payload={"role": "tool", "name": "get_env", "tool_call_id": "call-1"},
    )

    results = db.search("get_env")
    assert results and results[0]["session_id"] == session.session_id
    assert results[0]["role"] == "tool"
    db.close()

from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.session_store import attach_opt_in_session_store


def test_attach_opt_in_session_store_is_noop_when_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("UAGENT_SESSION_STORE", raising=False)
    core = SimpleNamespace(log_message=lambda message: None)

    store, session_id = attach_opt_in_session_store(
        core, project_path=tmp_path, entry_point="web"
    )
    assert store is None
    assert session_id is None
    assert not hasattr(core, "session_store")


def test_attach_opt_in_session_store_wraps_shared_log_callback(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(tmp_path / "sessions.sqlite3"))
    logged = []
    core = SimpleNamespace(log_message=logged.append)

    store, session_id = attach_opt_in_session_store(
        core, project_path=r"F:\\A\\agentcli", entry_point="web"
    )
    core.log_message({"role": "user", "content": "hello"})

    assert store is not None
    assert session_id
    assert logged
    assert store.list_messages(session_id)[0]["content"] == "hello"
    assert store.get_session(session_id)["project"] == "agentcli"
    store.close()

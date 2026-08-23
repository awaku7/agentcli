from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.session_store import (
    attach_opt_in_session_store,
    detach_opt_in_session_store,
)


def test_detach_closes_store_and_restores_log_callback(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(tmp_path / "sessions.sqlite3"))
    def original(message):
        del message

    core = SimpleNamespace(log_message=original)

    store, session_id = attach_opt_in_session_store(
        core, project_path=tmp_path, entry_point="a2a"
    )
    assert store is not None and session_id
    assert core.log_message is not original

    detach_opt_in_session_store(core)
    assert core.log_message is original
    assert not hasattr(core, "session_store")
    assert not hasattr(core, "session_id")

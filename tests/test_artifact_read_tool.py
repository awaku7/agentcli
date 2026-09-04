import json

import pytest

from uagent.runtime.artifact_manager import ArtifactManager
from uagent.runtime.session_store import SessionStore
from uagent.tools.artifact_read_tool import run_tool
from uagent.tools.context import ToolCallbacks


@pytest.fixture(autouse=True)
def _isolated_artifact_state(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path / "state"))


def _callbacks(monkeypatch, store, session_id):
    callbacks = ToolCallbacks(session_store=store, session_id=session_id)
    monkeypatch.setattr("uagent.tools.context._CALLBACKS", callbacks)


def test_reads_bounded_session_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        item = manager.register_text(
            "line 1\nline 2\nline 3\n",
            session_id=session.session_id,
        )
        _callbacks(monkeypatch, store, session.session_id)

        result = json.loads(
            run_tool(
                {
                    "artifact_id": f"artifact://{item.artifact_id}",
                    "start_line": 2,
                    "max_lines": 1,
                }
            )
        )

    assert result == {
        "ok": True,
        "artifact_id": item.artifact_id,
        "start_line": 2,
        "lines_read": 1,
        "has_more": True,
        "content_truncated": False,
        "content": "line 2\n",
    }


def test_limits_single_line_reads_and_preserves_line_numbers(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        item = manager.register_text(
            "x" * 100_000 + chr(10) + "last" + chr(10),
            session_id=session.session_id,
        )
        _callbacks(monkeypatch, store, session.session_id)

        result = json.loads(
            run_tool(
                {
                    "artifact_id": item.artifact_id,
                    "start_line": 2,
                    "max_lines": 1,
                    "max_chars": 100,
                }
            )
        )

    assert result["ok"] is True
    assert result["content"] == "last" + chr(10)
    assert result["lines_read"] == 1
    assert result["content_truncated"] is False


def test_rejects_artifact_from_another_session(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        owner = store.create_session(project="p", entry_point="owner")
        other = store.create_session(project="p", entry_point="other")
        item = manager.register_text("secret\n", session_id=owner.session_id)
        _callbacks(monkeypatch, store, other.session_id)

        result = json.loads(run_tool({"artifact_id": item.artifact_id}))

    assert result["ok"] is False
    assert "active session" in result["error"]

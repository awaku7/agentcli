import json

import pytest

from uagent.runtime.artifact_manager import ArtifactManager
from uagent.runtime.session_store import SessionStore
from uagent.tools.tool_policy import SideEffect, policy_for
from uagent.tools.artifact_export_tool import run_tool as export_artifact
from uagent.tools.artifact_info_tool import run_tool as artifact_info
from uagent.tools.artifact_read_tool import run_tool as read_artifact
from uagent.tools.context import ToolCallbacks


@pytest.fixture(autouse=True)
def _isolated_artifact_state(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_LANG", "en")
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))


def _callbacks(monkeypatch, store, session_id):
    callbacks = ToolCallbacks(session_store=store, session_id=session_id)
    monkeypatch.setattr("uagent.tools.context._CALLBACKS", callbacks)


def test_artifact_read_rejects_binary_without_decoding_it(tmp_path, monkeypatch):
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        source = tmp_path / "sample.bin"
        source.write_bytes(bytes([0, 255, 80, 78, 71, 137, 0]))
        item = manager.register(source, session_id=session.session_id)
        _callbacks(monkeypatch, store, session.session_id)

        result = json.loads(read_artifact({"artifact_id": item.artifact_id}))

    assert result["ok"] is False
    assert result["artifact_id"] == item.artifact_id
    assert result["media_type"] == "application/octet-stream"
    assert "artifact_info" in result["error"]
    assert "artifact_export" in result["error"]


def test_artifact_info_returns_binary_metadata(tmp_path, monkeypatch):
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        source = tmp_path / "sample.bin"
        source.write_bytes(bytes([0, 255]) + b"payload")
        item = manager.register(source, session_id=session.session_id)
        _callbacks(monkeypatch, store, session.session_id)

        result = json.loads(
            artifact_info({"artifact_id": f"artifact://{item.artifact_id}"})
        )

    assert result == {
        "ok": True,
        "artifact_id": item.artifact_id,
        "name": "sample.bin",
        "relative_path": "sample.bin",
        "stored_path": f"{item.artifact_id}/sample.bin",
        "media_type": "application/octet-stream",
        "extension": ".bin",
        "size": len(bytes([0, 255]) + b"payload"),
        "sha256": item.sha256,
        "created_at": item.created_at,
        "metadata": {},
    }


def test_artifact_export_preserves_binary_bytes(tmp_path, monkeypatch):
    payload = bytes(range(256))
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        source = tmp_path / "sample.bin"
        source.write_bytes(payload)
        item = manager.register(source, session_id=session.session_id)
        _callbacks(monkeypatch, store, session.session_id)

        result = json.loads(
            export_artifact(
                {
                    "artifact_id": item.artifact_id,
                    "output_path": "exports/copied.bin",
                }
            )
        )

    destination = tmp_path / "exports" / "copied.bin"
    assert result["ok"] is True
    assert result["output_path"] == "exports/copied.bin"
    assert result["media_type"] == "application/octet-stream"
    assert result["size"] == len(payload)
    assert destination.read_bytes() == payload
    assert result["sha256"] == item.sha256
    assert result["attachments"][0]["mime"] == "application/octet-stream"
    assert "data_base64" not in result["attachments"][0]


def test_artifact_export_rejects_path_outside_workdir(tmp_path, monkeypatch):
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        source = tmp_path / "sample.bin"
        source.write_bytes(b"payload")
        item = manager.register(source, session_id=session.session_id)
        _callbacks(monkeypatch, store, session.session_id)

        result = json.loads(
            export_artifact(
                {
                    "artifact_id": item.artifact_id,
                    "output_path": str(tmp_path.parent / "outside.bin"),
                }
            )
        )

    assert result["ok"] is False
    assert "workdir" in result["error"]


def test_artifact_policy_is_read_only_unless_overwriting():
    info_policy = policy_for("artifact_info", {})
    export_policy = policy_for("artifact_export", {"overwrite": False})
    overwrite_policy = policy_for("artifact_export", {"overwrite": True})

    assert info_policy.side_effect is SideEffect.READ_ONLY
    assert info_policy.parallel_safe is True
    assert export_policy.requires_confirmation is False
    assert overwrite_policy.side_effect is SideEffect.DESTRUCTIVE
    assert overwrite_policy.requires_confirmation is True

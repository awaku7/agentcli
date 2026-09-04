import hashlib

import pytest

from uagent.runtime.artifact_manager import (
    ArtifactManager,
    ArtifactManagerError,
)
from uagent.runtime.session_store import SessionStore


@pytest.fixture(autouse=True)
def _isolated_artifact_state(monkeypatch, tmp_path):
    monkeypatch.setenv("UAGENT_STATE_DIR", str(tmp_path / "state"))


def test_register_get_and_open_persists_metadata(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("hello", encoding="utf-8")
    with ArtifactManager(tmp_path) as manager:
        item = manager.register(source)
        assert item.size == 5
        assert item.sha256 == hashlib.sha256(b"hello").hexdigest()
        assert item.media_type == "text/plain"
        assert item.extension == ".txt"
        assert manager.open(item.artifact_id).read_text() == "hello"
        assert manager.get(item.artifact_id) == item


def test_register_rejects_external_and_directory(tmp_path):
    outside = tmp_path.parent / "outside-artifact.txt"
    outside.write_text("x", encoding="utf-8")
    with ArtifactManager(tmp_path) as manager:
        with pytest.raises(ArtifactManagerError):
            manager.register(outside)
        with pytest.raises(ArtifactManagerError):
            manager.register(tmp_path)
        valid = tmp_path / "valid.txt"
        valid.write_text("valid", encoding="utf-8")
        with pytest.raises(ArtifactManagerError, match="metadata must be an object"):
            manager.register(valid, metadata=["not", "an", "object"])


def test_private_store_uses_wal_and_artifact_indexes(tmp_path):
    with ArtifactManager(tmp_path) as manager:
        assert manager._connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert manager._connection.execute("PRAGMA synchronous").fetchone()[0] == 1
        indexes = {
            row["name"]
            for row in manager._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        assert {
            "idx_artifacts_session_created",
            "idx_artifacts_media_created",
        } <= indexes


def test_global_artifact_root_is_shared_across_workdirs(tmp_path):
    first_workdir = tmp_path / "first"
    second_workdir = tmp_path / "second"
    first_workdir.mkdir()
    second_workdir.mkdir()
    source = first_workdir / "result.txt"
    source.write_text("global artifact", encoding="utf-8")

    with ArtifactManager(first_workdir) as first:
        item = first.register(source)
        assert first.artifact_root == (tmp_path / "state" / "artifacts").resolve()
        assert (
            first.open(item.artifact_id).read_text(encoding="utf-8")
            == "global artifact"
        )

    with ArtifactManager(second_workdir) as second:
        assert second.get(item.artifact_id).stored_path == item.stored_path
        assert (
            second.open(item.artifact_id).read_text(encoding="utf-8")
            == "global artifact"
        )


def test_deleting_session_removes_new_global_artifacts(tmp_path):
    source = tmp_path / "result.txt"
    source.write_text("owned artifact", encoding="utf-8")
    with (
        SessionStore(tmp_path / "state" / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        item = manager.register(source, session_id=session.session_id)
        stored = tmp_path / "state" / "artifacts" / item.stored_path
        assert stored.is_file()

        store.delete_session(session.session_id)

        assert not stored.exists()
        with pytest.raises(ArtifactManagerError, match="unknown artifact"):
            manager.get(item.artifact_id)


def test_legacy_workdir_artifact_remains_readable_without_migration(tmp_path):
    workdir = tmp_path / "legacy"
    workdir.mkdir()
    artifact_id = "a" * 32
    legacy_dir = workdir / ".uag" / "artifacts" / artifact_id
    legacy_dir.mkdir(parents=True)
    payload = legacy_dir / "old.txt"
    payload.write_text("legacy artifact", encoding="utf-8")

    with (
        SessionStore(tmp_path / "state" / "sessions.sqlite3") as store,
        ArtifactManager(workdir, store=store) as manager,
    ):
        session = store.create_session(project="p", entry_point="test")
        manager._connection.execute(
            "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                session.session_id,
                "old.txt",
                "old.txt",
                f".uag/artifacts/{artifact_id}/old.txt",
                "text/plain",
                ".txt",
                len("legacy artifact"),
                hashlib.sha256(b"legacy artifact").hexdigest(),
                "2025-01-01 00:00:00",
                "{}",
            ),
        )
        assert (
            manager.open(artifact_id).read_text(encoding="utf-8") == "legacy artifact"
        )


def test_session_filter_and_attach(tmp_path):
    source = tmp_path / "result.json"
    source.write_text("{}", encoding="utf-8")
    db = tmp_path / "sessions.sqlite3"
    with SessionStore(db) as store, ArtifactManager(tmp_path, store=store) as manager:
        first = store.create_session(project="p", entry_point="cli")
        second = store.create_session(project="p", entry_point="web")
        item = manager.register(
            source, session_id=first.session_id, metadata={"kind": "result"}
        )
        assert [x.artifact_id for x in manager.list(session_id=first.session_id)] == [
            item.artifact_id
        ]
        assert manager.list(session_id=second.session_id) == []
        manager.attach(item.artifact_id, second.session_id)
        assert manager.list(session_id=first.session_id) == []
        assert manager.get(item.artifact_id).metadata == {"kind": "result"}


def test_session_validation_and_duplicate_names_do_not_overwrite(tmp_path):
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text("one", encoding="utf-8")
    two.write_text("two", encoding="utf-8")
    with (
        SessionStore(tmp_path / "sessions.sqlite3") as store,
        ArtifactManager(tmp_path, store=store) as manager,
    ):
        a = manager.register(one, name="same.txt")
        b = manager.register(two, name="same.txt")
        assert a.artifact_id != b.artifact_id
        assert manager.open(a.artifact_id).read_text() == "one"
        with pytest.raises(ArtifactManagerError):
            manager.attach(a.artifact_id, "missing-session")


def test_register_text_persists_utf8_result(tmp_path):
    text = "先頭\\n本文\\n末尾"
    with ArtifactManager(tmp_path) as manager:
        item = manager.register_text(
            text,
            metadata={"kind": "tool_result", "tool_name": "example"},
        )
        assert item.name == "tool-result.txt"
        assert item.media_type == "text/plain"
        assert manager.open(item.artifact_id).read_text(encoding="utf-8") == text
        assert item.metadata["kind"] == "tool_result"


def test_manager_reopens_private_store(tmp_path):
    source = tmp_path / "data.bin"
    source.write_bytes(b"data")
    with ArtifactManager(tmp_path) as manager:
        artifact_id = manager.register(source).artifact_id
    with ArtifactManager(tmp_path) as manager:
        assert manager.open(artifact_id).read_bytes() == b"data"
        assert len(manager.list()) == 1

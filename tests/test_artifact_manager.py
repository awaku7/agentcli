import hashlib

import pytest

from uagent.runtime.artifact_manager import (
    ArtifactManager,
    ArtifactManagerError,
)
from uagent.runtime.session_store import SessionStore


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


def test_session_filter_and_attach(tmp_path):
    source = tmp_path / "result.json"
    source.write_text("{}", encoding="utf-8")
    db = tmp_path / "sessions.sqlite3"
    with SessionStore(db) as store, ArtifactManager(tmp_path, store=store) as manager:
        first = store.create_session(project="p", entry_point="cli")
        second = store.create_session(project="p", entry_point="web")
        item = manager.register(source, session_id=first.session_id, metadata={"kind": "result"})
        assert [x.artifact_id for x in manager.list(session_id=first.session_id)] == [item.artifact_id]
        assert manager.list(session_id=second.session_id) == []
        manager.attach(item.artifact_id, second.session_id)
        assert manager.list(session_id=first.session_id) == []
        assert manager.get(item.artifact_id).metadata == {"kind": "result"}


def test_session_validation_and_duplicate_names_do_not_overwrite(tmp_path):
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text("one", encoding="utf-8")
    two.write_text("two", encoding="utf-8")
    with SessionStore(tmp_path / "sessions.sqlite3") as store, ArtifactManager(tmp_path, store=store) as manager:
        a = manager.register(one, name="same.txt")
        b = manager.register(two, name="same.txt")
        assert a.artifact_id != b.artifact_id
        assert manager.open(a.artifact_id).read_text() == "one"
        with pytest.raises(ArtifactManagerError):
            manager.attach(a.artifact_id, "missing-session")


def test_manager_reopens_private_store(tmp_path):
    source = tmp_path / "data.bin"
    source.write_bytes(b"data")
    with ArtifactManager(tmp_path) as manager:
        artifact_id = manager.register(source).artifact_id
    with ArtifactManager(tmp_path) as manager:
        assert manager.open(artifact_id).read_bytes() == b"data"
        assert len(manager.list()) == 1

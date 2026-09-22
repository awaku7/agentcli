from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError

import pytest

from uagent.runtime.identity_context import TurnContext
from uagent.runtime.memory_access import (
    MemoryAccessContext,
    MemoryAccessError,
    ScopedMemoryStore,
    map_legacy_owner,
)
from uagent.runtime.memory_store import MemoryStore, MemoryStoreConflictError


def context(principal="A", project="app", **kwargs):
    return MemoryAccessContext(
        principal_id=principal,
        project_id=project,
        authenticated=True,
        private_session=kwargs.pop("private_session", True),
        **kwargs,
    )


@pytest.fixture
def store(tmp_path):
    value = MemoryStore(tmp_path / "memory.sqlite3")
    yield value
    value.close()


def test_private_and_explicit_sharing_use_one_filter(store):
    a = ScopedMemoryStore(store, context("A"))
    b = ScopedMemoryStore(store, context("B"))
    c = ScopedMemoryStore(store, context("C"))
    first = a.append("shared reference")
    second = a.append("private reference")
    other = ScopedMemoryStore(store, context("A", "other")).append("other reference")
    assert b.records(query="reference") == []
    assert b.get(first["memory_id"]) is None
    grant = a.share(first["memory_id"], "B", expected_revision=1)
    assert a.share(first["memory_id"], "B", expected_revision=1) == grant
    assert b.count(query="reference") == 1
    assert b.export() == b.records(query="reference")
    shared = b.get(first["memory_id"])
    assert shared["owner_id"] == "A"
    assert shared["shared_reference"] is True
    assert shared["revision"] == 1
    assert shared["read_grant_id"] == grant
    assert not {"source", "source_id", "supersedes_id", "owner", "id"} & shared.keys()
    assert b.get(second["memory_id"]) is None
    assert b.get(other["memory_id"]) is None
    assert b.get("' OR 1=1 --") is None
    assert b.records(query="' OR 1=1 --") == []
    assert c.records() == []
    assert a.get(first["memory_id"])["shared_reference"] is False


@pytest.mark.parametrize("operation", ["update", "forget", "share", "revoke"])
def test_recipient_cannot_mutate_or_reshare(store, operation):
    a = ScopedMemoryStore(store, context("A"))
    b = ScopedMemoryStore(store, context("B"))
    record = a.append("A preference")
    memory_id = record["memory_id"]
    grant = a.share(memory_id, "B", expected_revision=1)
    before = b.access_generation
    with pytest.raises(MemoryAccessError):
        if operation == "update":
            b.update(memory_id, "B preference", expected_revision=1)
        elif operation == "forget":
            b.forget(memory_id, expected_revision=1)
        elif operation == "share":
            b.share(memory_id, "C", expected_revision=1)
        else:
            b.revoke(memory_id, grant)
    assert b.access_generation == before
    assert a.get(memory_id)["note"] == "A preference"
    assert not store.db.in_transaction


def test_revoke_changes_generation_and_only_removes_selected_recipient(store):
    a = ScopedMemoryStore(store, context("A"))
    b = ScopedMemoryStore(store, context("B"))
    c = ScopedMemoryStore(store, context("C"))
    memory_id = a.append("shared")["memory_id"]
    grant = a.share(memory_id, "B", expected_revision=1)
    a.share(memory_id, "C", expected_revision=1)
    before = b.access_generation
    a.revoke(memory_id, grant)
    assert b.access_generation > before
    assert b.records() == b.export() == []
    assert b.count() == 0 and b.get(memory_id) is None
    assert a.get(memory_id) is not None and c.get(memory_id) is not None
    revoked_generation = b.access_generation
    a.revoke(memory_id, grant)
    assert b.access_generation == revoked_generation
    new_grant = a.share(memory_id, "B", expected_revision=1)
    assert new_grant != grant
    assert b.get(memory_id) is not None
    assert a.get(memory_id)["revision"] == 1


@pytest.mark.parametrize("legacy_write", [False, True])
def test_update_requires_resharing_new_revision_and_forget_removes_all(
    store, legacy_write
):
    a = ScopedMemoryStore(store, context("A"))
    b = ScopedMemoryStore(store, context("B"))
    memory_id = a.append("version one")["memory_id"]
    a.share(memory_id, "B", expected_revision=1)
    before = b.access_generation
    if legacy_write:
        store.update_by_id(memory_id, "version two", expected_revision=1)
    else:
        a.update(memory_id, "version two", expected_revision=1)
    assert b.get(memory_id) is None
    assert b.access_generation > before
    with pytest.raises(MemoryStoreConflictError):
        a.share(memory_id, "B", expected_revision=1)
    a.share(memory_id, "B", expected_revision=2)
    assert b.get(memory_id)["note"] == "version two"
    before = b.access_generation
    if legacy_write:
        store.forget_by_id(memory_id, expected_revision=2)
    else:
        a.forget(memory_id, expected_revision=2)
    assert b.get(memory_id) is None
    assert b.access_generation > before
    assert store.db.execute("SELECT COUNT(*) FROM memory_grants").fetchone()[0] == 0


def test_failed_transaction_rolls_back_grant_and_generation(store):
    a = ScopedMemoryStore(store, context("A"))
    memory_id = a.append("shared")["memory_id"]
    before = a.access_generation
    store.db.execute(
        "CREATE TRIGGER fail_grant AFTER INSERT ON memory_grants "
        "BEGIN SELECT RAISE(ABORT, 'test rollback'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        a.share(memory_id, "B", expected_revision=1)
    assert a.access_generation == before
    assert store.db.execute("SELECT COUNT(*) FROM memory_grants").fetchone()[0] == 0
    assert not store.db.in_transaction


def test_direct_sharing_does_not_grant_project_or_shared_room_access(store):
    a = ScopedMemoryStore(store, context("A"))
    memory_id = a.append("A private information")["memory_id"]
    a.share(memory_id, "B", expected_revision=1)
    assert ScopedMemoryStore(store, context("B", "other")).get(memory_id) is None
    shared_room = ScopedMemoryStore(
        store,
        context(
            "B",
            private_session=False,
            room_id="room-X",
            readable_audiences=(("room", "room-X"),),
        ),
    )
    assert shared_room.records() == []
    # A's own private information also cannot become shared room output.
    assert ScopedMemoryStore(store, context("A", private_session=False)).records() == []
    with pytest.raises(MemoryAccessError):
        shared_room.append("do not expose personal write results in shared output")


def test_room_and_project_audiences_require_explicit_server_policy(store):
    # Trusted fixture setup represents a future RoomAccessPolicy write adapter.
    for kind, audience_id, project in [
        ("room", "X", "app"),
        ("room", "Y", "app"),
        ("project", "app", "app"),
        ("room", "X", "other"),
    ]:
        record = store.append(f"{kind}:{audience_id}:{project}", project=project)
        store.db.execute(
            "UPDATE memories SET owner_id='A', audience_type=?, audience_id=? "
            "WHERE memory_id=?",
            (kind, audience_id, record["memory_id"]),
        )
    store.db.commit()
    scoped = ScopedMemoryStore(
        store,
        context(
            "B",
            room_id="X",
            private_session=False,
            readable_audiences=(("room", "X"), ("project", "app")),
        ),
    )
    assert {r["note"] for r in scoped.records()} == {"room:X:app", "project:app:app"}
    assert ScopedMemoryStore(store, context("B", room_id="X")).records() == []


def test_legacy_migration_preserves_records_and_requires_explicit_mapping(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE memories(id INTEGER PRIMARY KEY, created_at REAL, "
            "note TEXT, owner TEXT, project TEXT)"
        )
        db.executemany(
            "INSERT INTO memories VALUES (?, 1, ?, ?, ?)",
            [
                (1, "known", "os-login", "app"),
                (2, "unknown", None, "app"),
                (3, "other project", "os-login", "other"),
            ],
        )
    store = MemoryStore(path)
    try:
        a = ScopedMemoryStore(store, context("os-login"))
        assert a.records() == []
        assert len(store.records()) == 3
        assert (
            map_legacy_owner(
                store, legacy_owner="os-login", principal_id="A", project_id="app"
            )
            == 1
        )
        assert (
            map_legacy_owner(
                store, legacy_owner="os-login", principal_id="A", project_id="app"
            )
            == 0
        )
        migrated = ScopedMemoryStore(store, context("A")).records()
        assert [r["memory_id"] for r in migrated] == ["legacy-1"]
        assert migrated[0]["note"] == "known" and migrated[0]["revision"] == 2
        assert store.db.execute("SELECT COUNT(*) FROM memory_grants").fetchone()[0] == 0
        assert a.records() == []
        with pytest.raises(ValueError):
            map_legacy_owner(store, legacy_owner="", principal_id="A", project_id="app")
        generation = a.access_generation
    finally:
        store.close()
    reopened = MemoryStore(path)
    try:
        assert ScopedMemoryStore(reopened, context("A")).access_generation == generation
        assert len(reopened.records()) == 3
    finally:
        reopened.close()


def test_revoke_is_visible_across_store_connections(store):
    other = MemoryStore(store.path)
    try:
        a = ScopedMemoryStore(store, context("A"))
        b = ScopedMemoryStore(other, context("B"))
        memory_id = a.append("shared")["memory_id"]
        grant = a.share(memory_id, "B", expected_revision=1)
        assert b.get(memory_id) is not None
        generation = b.access_generation
        a.revoke(memory_id, grant)
        assert b.get(memory_id) is None
        assert b.access_generation > generation
    finally:
        other.close()


def test_context_cannot_expand_to_another_personal_or_room_audience():
    for audiences in [(("personal", "A"),), (("room", "Y"),), (("project", "other"),)]:
        with pytest.raises(MemoryAccessError):
            context("B", room_id="X", readable_audiences=audiences)
    with pytest.raises(MemoryAccessError):
        MemoryAccessContext(principal_id="A", project_id="app", authenticated=False)
    with pytest.raises(ValueError):
        context("A", "")
    turn = TurnContext(
        principal_id="A",
        room_id="X",
        project_id="app",
        session_id="s",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
    )
    ctx = MemoryAccessContext.from_turn(turn)
    assert not ctx.private_session
    with pytest.raises(FrozenInstanceError):
        ctx.principal_id = "B"


def test_unknown_ids_and_stale_versions_do_not_mutate(store):
    a = ScopedMemoryStore(store, context("A"))
    record = a.append("one")
    a.update(record["memory_id"], "two", expected_revision=1)
    generation = a.access_generation
    with pytest.raises(MemoryStoreConflictError):
        a.forget(record["memory_id"], expected_revision=1)
    with pytest.raises(MemoryAccessError):
        a.revoke(record["memory_id"], "unknown-grant")
    with pytest.raises(MemoryAccessError):
        a.forget("unknown-memory", expected_revision=1)
    assert a.access_generation == generation
    assert a.get(record["memory_id"])["note"] == "two"

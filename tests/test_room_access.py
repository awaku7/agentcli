from __future__ import annotations

import pytest

from uagent.runtime.memory_access import MemoryAccessError
from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.room_access import RoomAccessPolicy, RoomMemoryService


@pytest.fixture
def store(tmp_path):
    value = MemoryStore(tmp_path / "memory.sqlite3")
    yield value
    value.close()


def test_room_id_alone_does_not_grant_access(store):
    policy = RoomAccessPolicy(store, admin_principals=frozenset({"root"}))
    service = RoomMemoryService(
        store,
        policy,
        principal_id="alice",
        project_id="demo",
        room_id="room-x",
    )

    assert policy.can_join("alice", "room-x") is False
    with pytest.raises(MemoryAccessError, match="read is not permitted"):
        service.records()
    with pytest.raises(MemoryAccessError, match="write is not permitted"):
        service.append("not authorized")


def test_roles_control_room_memory_and_member_changes_invalidate_generation(store):
    policy = RoomAccessPolicy(store, admin_principals=frozenset({"root"}))
    before = int(
        store.db.execute(
            "SELECT value FROM memory_metadata WHERE key='access_generation'"
        ).fetchone()[0]
    )
    policy.set_membership("root", "room-x", "alice", "admin")
    policy.set_membership("alice", "room-x", "bob", "member")
    assert policy.can_join("bob", "room-x") is True
    assert policy.can_write_room_memory("bob", "room-x") is False
    assert (
        int(
            store.db.execute(
                "SELECT value FROM memory_metadata WHERE key='access_generation'"
            ).fetchone()[0]
        )
        > before
    )

    alice = RoomMemoryService(
        store,
        policy,
        principal_id="alice",
        project_id="demo",
        room_id="room-x",
    )
    bob = RoomMemoryService(
        store,
        policy,
        principal_id="bob",
        project_id="demo",
        room_id="room-x",
    )
    record = alice.append("shared room rule")
    assert [item["note"] for item in bob.records()] == ["shared room rule"]
    with pytest.raises(MemoryAccessError, match="write is not permitted"):
        bob.update(record["memory_id"], "changed", expected_revision=1)
    with pytest.raises(MemoryAccessError, match="delete is not permitted"):
        bob.forget(record["memory_id"], expected_revision=1)


def test_editor_can_delete_only_own_room_memory_and_last_admin_is_retained(store):
    policy = RoomAccessPolicy(store, admin_principals=frozenset({"root"}))
    policy.set_membership("root", "room-x", "alice", "admin")
    policy.set_membership("alice", "room-x", "bob", "editor")
    alice = RoomMemoryService(
        store,
        policy,
        principal_id="alice",
        project_id="demo",
        room_id="room-x",
    )
    bob = RoomMemoryService(
        store,
        policy,
        principal_id="bob",
        project_id="demo",
        room_id="room-x",
    )
    alice_record = alice.append("admin record")
    bob_record = bob.append("editor record")

    with pytest.raises(MemoryAccessError, match="delete is not permitted"):
        bob.forget(alice_record["memory_id"], expected_revision=1)
    bob.forget(bob_record["memory_id"], expected_revision=1)
    with pytest.raises(MemoryAccessError, match="last room admin"):
        policy.revoke_membership("root", "room-x", "alice")

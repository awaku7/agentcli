from __future__ import annotations

import pytest

from uagent.runtime.memory_access import MemoryAccessError
from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.project_access import ProjectAccessPolicy


def test_project_membership_is_server_side_and_role_bound(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    policy = ProjectAccessPolicy(store, admin_principals=frozenset({"root"}))

    policy.set_membership("root", "demo", "alice", "editor")
    policy.set_membership("root", "demo", "bob", "viewer")

    assert policy.can_access("alice", "demo", "editor")
    assert policy.can_access("bob", "demo", "viewer")
    assert not policy.can_access("bob", "demo", "editor")
    assert not policy.can_access("alice", "other", "viewer")
    policy.bind_room("root", "demo", "room-x")
    assert policy.room_project("room-x") == "demo"
    policy.require_room_binding("demo", "room-x")
    with pytest.raises(MemoryAccessError):
        policy.require_access("alice", "other")
    store.close()


def test_project_membership_cannot_remove_last_admin(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    policy = ProjectAccessPolicy(store, admin_principals=frozenset({"root"}))
    policy.set_membership("root", "demo", "alice", "admin")

    with pytest.raises(MemoryAccessError, match="last project admin"):
        policy.revoke_membership("alice", "demo", "alice")
    store.close()

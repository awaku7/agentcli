from __future__ import annotations

from uagent.runtime.enterprise_identity import (
    GroupPolicyAssignments,
    register_directory_group_policy_adapter,
)
from uagent.runtime.identity_context import IdentityContext
from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.project_access import ProjectAccessPolicy


class _DirectoryPolicy:
    def map_groups(self, identity, groups):
        assert groups == ("engineering",)
        return GroupPolicyAssignments(
            room_roles=(("room-x", "editor"),),
            project_ids=("demo",),
        )


class _NoGroupsPolicy:
    def map_groups(self, identity, groups):
        return GroupPolicyAssignments()


def test_environment_directory_group_policy_adapter(monkeypatch):
    import json

    from uagent.runtime.enterprise_identity import directory_group_policy_assignments

    monkeypatch.setenv(
        "UAGENT_DIRECTORY_GROUP_POLICY",
        json.dumps(
            {
                "groups": {
                    "engineering": {
                        "projects": ["demo"],
                        "rooms": {"room-x": "editor"},
                    }
                }
            }
        ),
    )
    identity = IdentityContext("user", True, "windows_ad", groups=("engineering",))
    assignments = directory_group_policy_assignments(identity)
    assert assignments.project_ids == ("demo",)
    assert assignments.room_roles == (("room-x", "editor"),)


def test_directory_group_assignments_sync_without_storing_groups(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    policy = ProjectAccessPolicy(store, admin_principals=frozenset({"root"}))
    policy.set_membership("root", "demo", "root", "admin")
    policy.bind_room("root", "demo", "room-x")
    identity = IdentityContext("user", True, "windows_ad", groups=("engineering",))
    register_directory_group_policy_adapter(_DirectoryPolicy())
    try:
        policy.sync_directory_policy(identity)
        assert policy.can_access("user", "demo", "viewer")
        room_membership = store.db.execute(
            "SELECT role, granted_by FROM room_memberships "
            "WHERE room_id = 'room-x' AND principal_id = 'user'"
        ).fetchone()
        assert dict(room_membership) == {
            "role": "editor",
            "granted_by": "directory-policy",
        }
        stored_groups = store.db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE '%group%'"
        ).fetchall()
        assert stored_groups == []
    finally:
        register_directory_group_policy_adapter(None)
        store.close()


def test_environment_directory_group_policy_rejects_string_boolean():
    import pytest

    from uagent.runtime.enterprise_identity import (
        EnvironmentDirectoryGroupPolicyAdapter,
        IdentityConfigurationError,
    )

    with pytest.raises(IdentityConfigurationError):
        EnvironmentDirectoryGroupPolicyAdapter(
            '{"groups":{"engineering":{"administrator":"false"}}}'
        )


def test_directory_group_sync_reconciles_stale_policy_access(tmp_path):
    from uagent.runtime.room_access import RoomAccessPolicy

    store = MemoryStore(tmp_path / "memory.sqlite3")
    policy = ProjectAccessPolicy(store, admin_principals=frozenset({"root"}))
    policy.set_membership("root", "demo", "root", "admin")
    policy.bind_room("root", "demo", "room-x")
    identity = IdentityContext("user", True, "windows_ad", groups=("engineering",))
    register_directory_group_policy_adapter(_DirectoryPolicy())
    try:
        policy.sync_directory_policy(identity)
        assert policy.can_access("user", "demo", "viewer")
        assert RoomAccessPolicy(store).can_join("user", "room-x")

        other = IdentityContext("other", True, "windows_ad", groups=("engineering",))
        policy.sync_directory_policy(other)
        assert policy.can_access("other", "demo", "viewer")

        policy.set_membership("root", "demo", "user", "editor")
        RoomAccessPolicy(store, admin_principals=frozenset({"root"})).set_membership(
            "root", "room-x", "user", "editor"
        )
        register_directory_group_policy_adapter(_NoGroupsPolicy())
        policy.sync_directory_policy(other)
        policy.sync_directory_policy(
            IdentityContext("other", True, "windows_ad", groups=())
        )
        assert not policy.can_access("other", "demo", "viewer")
        assert policy.can_access("user", "demo", "editor")
        assert RoomAccessPolicy(store).can_join("user", "room-x")
    finally:
        register_directory_group_policy_adapter(None)
        store.close()

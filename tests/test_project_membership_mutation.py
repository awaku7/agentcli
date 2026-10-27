"""Transaction/fail-closed regression coverage for PR-C0 membership mutations."""

from __future__ import annotations

import sqlite3

import pytest

from uagent.runtime.memory_access import MemoryAccessError
from uagent.runtime.memory_store import MemoryStore, MemoryStoreConflictError
from uagent.runtime.project_access import ProjectAccessPolicy
from uagent.runtime.project_membership_mutation import apply_membership_change


@pytest.fixture
def enrolled(tmp_path):
    store = MemoryStore(tmp_path / "audit.sqlite3")
    policy = ProjectAccessPolicy(store, admin_principals=frozenset({"bootstrap"}))
    policy.set_membership("bootstrap", "project-a", "alice", "admin")
    policy.set_membership("bootstrap", "project-a", "bob", "viewer")
    policy.set_membership("bootstrap", "project-a", "second", "admin")
    yield store
    store.close()


def change(
    store,
    *,
    actor="alice",
    target="bob",
    role="editor",
    revision=1,
    action="grant",
    project="project-a",
):
    return apply_membership_change(
        store.db,
        actor_principal_id=actor,
        project_id=project,
        target_principal_id=target,
        expected_revision=revision,
        action=action,
        role=role if action == "grant" else None,
    )


def test_grant_revision_audit_are_one_transaction(enrolled):
    outcome = change(enrolled)
    assert outcome.role == "editor"
    assert outcome.status == "active"
    assert outcome.revision == 2
    row = enrolled.db.execute(
        "SELECT role, status, revision, granted_by FROM project_memberships "
        "WHERE project_id = 'project-a' AND principal_id = 'bob'"
    ).fetchone()
    assert tuple(row) == ("editor", "active", 2, "alice")
    audit = enrolled.db.execute(
        "SELECT actor_principal_id, previous_role, new_role, previous_revision, new_revision "
        "FROM project_membership_mutation_audit"
    ).fetchone()
    assert tuple(audit) == ("alice", "viewer", "editor", 1, 2)


def test_revision_compare_and_swap_rejects_stale_and_noop(enrolled):
    change(enrolled)
    with pytest.raises(MemoryStoreConflictError, match="revision"):
        change(enrolled)
    with pytest.raises(MemoryStoreConflictError, match="unchanged"):
        change(enrolled, revision=2)
    count = enrolled.db.execute(
        "SELECT COUNT(*) FROM project_membership_mutation_audit"
    ).fetchone()[0]
    assert count == 1


def test_revoked_membership_revision_survives_and_prevents_aba(enrolled):
    revoked = change(enrolled, action="revoke")
    assert revoked.status == "revoked"
    assert revoked.revision == 2
    with pytest.raises(MemoryStoreConflictError):
        change(enrolled, revision=1)
    restored = change(enrolled, revision=2, role="viewer")
    assert restored.revision == 3
    assert restored.status == "active"
    assert (
        enrolled.db.execute(
            "SELECT COUNT(*) FROM project_membership_mutation_audit"
        ).fetchone()[0]
        == 2
    )


def test_last_manual_admin_cannot_be_revoked_or_demoted(enrolled):
    change(enrolled, target="second", action="revoke")
    with pytest.raises(MemoryAccessError, match="last manual admin"):
        change(enrolled, target="alice", action="revoke")
    with pytest.raises(MemoryAccessError, match="last manual admin"):
        change(enrolled, target="alice", role="viewer")
    row = enrolled.db.execute(
        "SELECT role, status, revision FROM project_memberships "
        "WHERE project_id = 'project-a' AND principal_id = 'alice'"
    ).fetchone()
    assert tuple(row) == ("admin", "active", 1)


def test_actor_authority_is_checked_in_write_transaction(enrolled):
    with pytest.raises(MemoryAccessError, match="explicit active project admin"):
        change(enrolled, actor="bob", target="alice", role="viewer")
    enrolled.db.execute(
        "UPDATE project_memberships SET status='revoked' "
        "WHERE project_id='project-a' AND principal_id='alice'"
    )
    enrolled.db.commit()
    with pytest.raises(MemoryAccessError):
        change(enrolled, target="bob", revision=1)
    assert (
        enrolled.db.execute(
            "SELECT COUNT(*) FROM project_membership_mutation_audit"
        ).fetchone()[0]
        == 0
    )


def test_directory_managed_grants_and_admin_cannot_be_used_for_manual_write(enrolled):
    enrolled.db.execute(
        "UPDATE project_memberships SET granted_by='directory-policy' "
        "WHERE project_id='project-a' AND principal_id='bob'"
    )
    enrolled.db.commit()
    with pytest.raises(MemoryAccessError, match="directory-managed"):
        change(enrolled)
    enrolled.db.execute(
        "UPDATE project_memberships SET granted_by='directory-policy' "
        "WHERE project_id='project-a' AND principal_id='alice'"
    )
    enrolled.db.commit()
    with pytest.raises(MemoryAccessError, match="explicit active project admin"):
        change(enrolled, target="second", role="viewer")


def test_failed_audit_insertion_rolls_back_membership(enrolled):
    enrolled.db.execute(
        "CREATE TRIGGER reject_mutation_audit BEFORE INSERT "
        "ON project_membership_mutation_audit "
        "BEGIN SELECT RAISE(FAIL, 'audit store unavailable'); END"
    )
    enrolled.db.commit()
    with pytest.raises(sqlite3.IntegrityError, match="audit store unavailable"):
        change(enrolled)
    row = enrolled.db.execute(
        "SELECT role, revision FROM project_memberships "
        "WHERE project_id='project-a' AND principal_id='bob'"
    ).fetchone()
    assert tuple(row) == ("viewer", 1)


def test_create_revision_zero_and_project_isolation(enrolled):
    result = change(enrolled, target="new-person", revision=0, role="viewer")
    assert result.revision == 1
    with pytest.raises(MemoryStoreConflictError):
        change(enrolled, target="new-person", revision=0)
    with pytest.raises(MemoryAccessError, match="active"):
        change(enrolled, target="new-person", project="project-b", revision=1)


def test_bad_inputs_are_rejected_before_transaction(enrolled):
    for kwargs in (
        {"revision": -1},
        {"revision": True},
        {"role": "owner"},
        {"action": "revoke", "role": None, "revision": 999},
    ):
        with pytest.raises((ValueError, MemoryStoreConflictError)):
            change(enrolled, **kwargs)
    assert not enrolled.db.in_transaction

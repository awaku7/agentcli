"""Strict, transactional core for future delegated management membership writes.

This module does not authenticate HTTP callers. Only callers that already
verified the immutable UAG actor principal should invoke it.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import time

from .memory_access import MemoryAccessError
from .memory_store import MemoryStoreConflictError

ROLES = frozenset({"viewer", "editor", "admin"})


@dataclass(frozen=True)
class VerifiedOperator:
    """Signed and already verified by the C1 HTTP adapter, never user input."""

    issuer_id: str
    actor_user_id: int
    session_version: int
    nonce: str


@dataclass(frozen=True)
class MembershipChange:
    project_id: str
    principal_id: str
    role: str | None
    status: str
    revision: int


def apply_membership_change(
    conn: sqlite3.Connection,
    *,
    actor_principal_id: str,
    project_id: str,
    target_principal_id: str,
    expected_revision: int,
    action: str,
    role: str | None = None,
    operator: VerifiedOperator | None = None,
) -> MembershipChange:
    """Check admin authority and revision inside the same write transaction.

    Directory-policy memberships are managed by the authoritative directory,
    never by this manual remote-management backend. A missing row has revision
    zero; revoked rows retain their revision to prevent ABA on re-grant.
    """
    if (
        not isinstance(project_id, str)
        or not 1 <= len(project_id) <= 128
        or project_id.strip() != project_id
        or not isinstance(target_principal_id, str)
        or not 1 <= len(target_principal_id) <= 256
        or target_principal_id.strip() != target_principal_id
        or not isinstance(actor_principal_id, str)
        or not 1 <= len(actor_principal_id) <= 256
        or actor_principal_id.strip() != actor_principal_id
    ):
        raise ValueError("invalid actor, target or project")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("expected_revision must be nonnegative integer")
    if not isinstance(action, str) or action not in {"grant", "revoke"}:
        raise ValueError("invalid membership action")
    if action == "grant":
        if not isinstance(role, str) or role not in ROLES:
            raise ValueError("invalid project role")
    elif role is not None:
        raise ValueError("revoke must not specify a role")

    if operator is not None and (
        not isinstance(operator, VerifiedOperator)
        or not isinstance(operator.issuer_id, str)
        or not 1 <= len(operator.issuer_id) <= 128
        or type(operator.actor_user_id) is not int
        or operator.actor_user_id <= 0
        or type(operator.session_version) is not int
        or operator.session_version < 0
        or not isinstance(operator.nonce, str)
        or not 16 <= len(operator.nonce) <= 128
    ):
        raise ValueError("invalid verified operator")

    conn.execute("BEGIN IMMEDIATE")
    try:
        project = conn.execute(
            "SELECT status FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if project is None or project["status"] != "active":
            raise MemoryAccessError("project must be active")
        # Even global admin env or an old directory-policy snapshot is NOT
        # sufficient for delegated remote writes.
        actor = conn.execute(
            "SELECT role, granted_by FROM project_memberships "
            "WHERE project_id = ? AND principal_id = ? AND status = 'active'",
            (project_id, actor_principal_id),
        ).fetchone()
        if (
            actor is None
            or actor["role"] != "admin"
            or actor["granted_by"] == "directory-policy"
        ):
            raise MemoryAccessError("explicit active project admin required")

        target = conn.execute(
            "SELECT role, status, revision, granted_by FROM project_memberships "
            "WHERE project_id = ? AND principal_id = ?",
            (project_id, target_principal_id),
        ).fetchone()
        current_revision = int(target["revision"]) if target else 0
        if current_revision != expected_revision:
            raise MemoryStoreConflictError("membership revision conflict")
        if target is not None and target["granted_by"] == "directory-policy":
            raise MemoryAccessError("directory-managed membership is read-only")
        before_role = str(target["role"]) if target else None
        before_status = str(target["status"]) if target else "absent"
        if action == "revoke":
            if target is None or target["status"] != "active":
                raise MemoryStoreConflictError("membership is not active")
            new_role = None
            new_status = "revoked"
        else:
            if target and target["status"] == "active" and target["role"] == role:
                raise MemoryStoreConflictError("membership is unchanged")
            new_role = role
            new_status = "active"

        # Demoting and revoking use the same last-admin floor, and exclude
        # directory-derived admin grants as replacements.
        if (
            target is not None
            and target["status"] == "active"
            and target["role"] == "admin"
            and new_role != "admin"
        ):
            count = conn.execute(
                "SELECT COUNT(*) FROM project_memberships "
                "WHERE project_id = ? AND status = 'active' AND role = 'admin' "
                "AND granted_by <> 'directory-policy'",
                (project_id,),
            ).fetchone()[0]
            if count <= 1:
                raise MemoryAccessError("cannot remove or demote the last manual admin")

        now = time.time()
        if operator is not None:
            # Replay consumption, the mutation and audit must commit together.
            conn.execute(
                "INSERT INTO project_membership_mutation_nonces "
                "(issuer_id, nonce, consumed_at) VALUES (?, ?, ?)",
                (operator.issuer_id, operator.nonce, now),
            )
        if target is None:
            assert new_role is not None
            conn.execute(
                "INSERT INTO project_memberships "
                "(project_id, principal_id, role, status, revision, granted_by, "
                "created_at, updated_at) VALUES (?, ?, ?, 'active', 1, ?, ?, ?)",
                (
                    project_id,
                    target_principal_id,
                    new_role,
                    actor_principal_id,
                    now,
                    now,
                ),
            )
        else:
            conn.execute(
                "UPDATE project_memberships SET role = ?, status = ?, "
                "revision = revision + 1, granted_by = ?, updated_at = ? "
                "WHERE project_id = ? AND principal_id = ? AND revision = ?",
                (
                    new_role or before_role,
                    new_status,
                    actor_principal_id,
                    now,
                    project_id,
                    target_principal_id,
                    current_revision,
                ),
            )

        revision = current_revision + 1
        conn.execute(
            "INSERT INTO project_membership_mutation_audit "
            "(actor_principal_id, project_id, target_principal_id, "
            "previous_role, previous_status, new_role, new_status, "
            "previous_revision, new_revision, created_at, "
            "delegation_issuer, delegation_actor_user_id, "
            "delegation_session_version, delegation_nonce) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                actor_principal_id,
                project_id,
                target_principal_id,
                before_role,
                before_status,
                new_role,
                new_status,
                current_revision,
                revision,
                now,
                operator.issuer_id if operator else None,
                operator.actor_user_id if operator else None,
                operator.session_version if operator else None,
                operator.nonce if operator else None,
            ),
        )
        conn.commit()
        return MembershipChange(
            project_id, target_principal_id, new_role, new_status, revision
        )
    except Exception:
        conn.rollback()
        raise

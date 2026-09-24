"""Server-side project membership and authorization policy."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from ..env_utils import env_get
from .memory_access import MemoryAccessContext, MemoryAccessError, ScopedMemoryStore
from .memory_store import MemoryStore

PROJECT_ROLES = ("viewer", "editor", "admin")
_ROLE_RANK = {role: index for index, role in enumerate(PROJECT_ROLES)}


@dataclass(frozen=True)
class ProjectMembership:
    project_id: str
    principal_id: str
    role: str
    revision: int


def configured_admin_principals() -> frozenset[str]:
    raw = str(env_get("UAGENT_ADMIN_PRINCIPALS", "") or "")
    return frozenset(value.strip() for value in raw.split(",") if value.strip())


class ProjectAccessPolicy:
    """Authorize project-scoped operations before room/audience filtering."""

    def __init__(
        self, store: MemoryStore, *, admin_principals: frozenset[str] | None = None
    ) -> None:
        self._store = store
        self._admins = admin_principals or configured_admin_principals()

    def is_global_admin(self, principal_id: str) -> bool:
        return bool(principal_id and principal_id in self._admins)

    def membership(
        self, principal_id: str, project_id: str
    ) -> ProjectMembership | None:
        row = self._store.db.execute(
            "SELECT project_id, principal_id, role, revision "
            "FROM project_memberships WHERE project_id = ? AND principal_id = ? "
            "AND status = 'active'",
            (project_id, principal_id),
        ).fetchone()
        return ProjectMembership(**dict(row)) if row is not None else None

    def can_access(
        self, principal_id: str, project_id: str, role: str = "viewer"
    ) -> bool:
        if role not in _ROLE_RANK:
            raise ValueError("invalid project role")
        if self.is_global_admin(principal_id):
            return True
        membership = self.membership(principal_id, project_id)
        return (
            membership is not None and _ROLE_RANK[membership.role] >= _ROLE_RANK[role]
        )

    def require_access(
        self, principal_id: str, project_id: str, role: str = "viewer"
    ) -> None:
        if not self.can_access(principal_id, project_id, role):
            raise MemoryAccessError("project access is not permitted")

    def sync_directory_policy(self, identity: Any) -> None:
        """Apply and reconcile trusted directory assignments.

        Only rows still marked ``directory-policy`` are reconciled. Manual
        memberships therefore survive both policy refreshes and group removal.
        """
        from .enterprise_identity import (
            directory_group_policy_assignments,
            directory_group_policy_is_configured,
        )

        if not directory_group_policy_is_configured():
            return
        assignments = directory_group_policy_assignments(identity)
        project_ids = tuple(
            sorted(
                {
                    str(value).strip()
                    for value in assignments.project_ids
                    if str(value).strip()
                }
            )
        )
        room_roles = tuple(
            (str(room_id).strip(), str(role).strip().lower())
            for room_id, role in assignments.room_roles
            if str(room_id).strip()
            and str(role).strip().lower() in {"admin", "editor", "member"}
        )
        valid_room_roles: dict[str, str] = {}
        for room_id, room_role in room_roles:
            private_row = self._store.db.execute(
                "SELECT 1 FROM private_rooms WHERE room_id = ?", (room_id,)
            ).fetchone()
            if private_row is not None:
                continue
            project_row = self._store.db.execute(
                "SELECT project_id FROM room_projects WHERE room_id = ?", (room_id,)
            ).fetchone()
            if (
                project_row is not None
                and str(project_row["project_id"]) in project_ids
            ):
                valid_room_roles[room_id] = room_role

        role = "admin" if assignments.administrator else "viewer"
        now = time.time()
        self._store.db.execute("BEGIN IMMEDIATE")
        try:
            project_stale_sql = (
                "UPDATE project_memberships SET status='revoked', "
                "revision=revision + 1, updated_at=? "
                "WHERE principal_id=? AND status='active' "
                "AND granted_by='directory-policy'"
            )
            project_stale_params: tuple[Any, ...] = (now, identity.principal_id)
            if project_ids:
                placeholders = ",".join("?" for _ in project_ids)
                project_stale_sql += f" AND project_id NOT IN ({placeholders})"
                project_stale_params += project_ids
            self._store.db.execute(project_stale_sql, project_stale_params)

            room_stale_sql = (
                "UPDATE room_memberships SET status='revoked', "
                "revision=revision + 1, updated_at=? "
                "WHERE principal_id=? AND status='active' "
                "AND granted_by='directory-policy'"
            )
            room_stale_params: tuple[Any, ...] = (now, identity.principal_id)
            if valid_room_roles:
                placeholders = ",".join("?" for _ in valid_room_roles)
                room_stale_sql += f" AND room_id NOT IN ({placeholders})"
                room_stale_params += tuple(valid_room_roles)
            self._store.db.execute(room_stale_sql, room_stale_params)

            for project_id in project_ids:
                self._store.db.execute(
                    "INSERT OR IGNORE INTO projects(project_id, status, created_at, updated_at) "
                    "VALUES (?, 'active', ?, ?)",
                    (project_id, now, now),
                )
                existing = self._store.db.execute(
                    "SELECT role, granted_by FROM project_memberships "
                    "WHERE project_id = ? AND principal_id = ? AND status = 'active'",
                    (project_id, identity.principal_id),
                ).fetchone()
                if (
                    existing is not None
                    and existing["granted_by"] != "directory-policy"
                ):
                    continue
                assigned_role = role
                if (
                    existing is not None
                    and _ROLE_RANK[existing["role"]] > _ROLE_RANK[assigned_role]
                ):
                    assigned_role = existing["role"]
                self._store.db.execute(
                    "INSERT INTO project_memberships(project_id, principal_id, role, status, "
                    "revision, granted_by, created_at, updated_at) VALUES (?, ?, ?, 'active', "
                    "1, 'directory-policy', ?, ?) ON CONFLICT(project_id, principal_id) DO UPDATE SET "
                    "role=excluded.role, status='active', revision=project_memberships.revision + 1, "
                    "granted_by=excluded.granted_by, updated_at=excluded.updated_at",
                    (project_id, identity.principal_id, assigned_role, now, now),
                )

            for room_id, room_role in valid_room_roles.items():
                existing = self._store.db.execute(
                    "SELECT granted_by FROM room_memberships "
                    "WHERE room_id = ? AND principal_id = ? AND status = 'active'",
                    (room_id, identity.principal_id),
                ).fetchone()
                if (
                    existing is not None
                    and existing["granted_by"] != "directory-policy"
                ):
                    continue
                self._store.db.execute(
                    "INSERT INTO room_memberships(room_id, principal_id, role, status, "
                    "granted_by, created_at, updated_at) VALUES (?, ?, ?, 'active', "
                    "'directory-policy', ?, ?) ON CONFLICT(room_id, principal_id) DO UPDATE SET "
                    "role=excluded.role, status='active', revision=room_memberships.revision + 1, "
                    "granted_by=excluded.granted_by, updated_at=excluded.updated_at",
                    (room_id, identity.principal_id, room_role, now, now),
                )
            self._store.db.commit()
        except Exception:
            self._store.db.rollback()
            raise

    def room_project(self, room_id: str) -> str | None:
        row = self._store.db.execute(
            "SELECT project_id FROM room_projects WHERE room_id = ?",
            (room_id,),
        ).fetchone()
        return str(row["project_id"]) if row is not None else None

    def require_room_binding(self, project_id: str, room_id: str) -> None:
        bound_project = self.room_project(room_id)
        if bound_project != project_id:
            raise MemoryAccessError("room is not bound to this project")

    def bind_room(self, actor_id: str, project_id: str, room_id: str) -> None:
        project_id = str(project_id or "").strip()
        room_id = str(room_id or "").strip()
        if not project_id or not room_id:
            raise ValueError("project_id and room_id are required")
        if not self.can_access(actor_id, project_id, "admin"):
            raise MemoryAccessError("room binding operation is not permitted")
        now = time.time()
        self._store.db.execute("BEGIN IMMEDIATE")
        try:
            self._store.db.execute(
                "INSERT OR IGNORE INTO projects(project_id, status, created_at, updated_at) "
                "VALUES (?, 'active', ?, ?)",
                (project_id, now, now),
            )
            existing = self.room_project(room_id)
            if existing is not None and existing != project_id:
                raise MemoryAccessError("room is already bound to another project")
            self._store.db.execute(
                "INSERT INTO room_projects(room_id, project_id, revision, bound_by, "
                "created_at, updated_at) VALUES (?, ?, 1, ?, ?, ?) "
                "ON CONFLICT(room_id) DO UPDATE SET revision=room_projects.revision + 1, "
                "bound_by=excluded.bound_by, updated_at=excluded.updated_at",
                (room_id, project_id, actor_id, now, now),
            )
            self._store.db.commit()
        except Exception:
            self._store.db.rollback()
            raise

    def list_members(self, actor_id: str, project_id: str) -> list[dict[str, Any]]:
        if not self.can_access(actor_id, project_id, "admin"):
            raise MemoryAccessError("project membership operation is not permitted")
        rows = self._store.db.execute(
            "SELECT project_id, principal_id, role, status, revision, granted_by, "
            "created_at, updated_at FROM project_memberships "
            "WHERE project_id = ? AND status = 'active' ORDER BY principal_id",
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def set_membership(
        self, actor_id: str, project_id: str, principal_id: str, role: str
    ) -> ProjectMembership:
        project_id = str(project_id or "").strip()
        principal_id = str(principal_id or "").strip()
        role = str(role or "").strip().lower()
        if not project_id or not principal_id or role not in PROJECT_ROLES:
            raise ValueError("project_id, principal_id, and a valid role are required")
        if not self.is_global_admin(actor_id) and not self.can_access(
            actor_id, project_id, "admin"
        ):
            raise MemoryAccessError("project membership operation is not permitted")
        now = time.time()
        self._store.db.execute("BEGIN IMMEDIATE")
        try:
            self._store.db.execute(
                "INSERT OR IGNORE INTO projects(project_id, status, created_at, updated_at) "
                "VALUES (?, 'active', ?, ?)",
                (project_id, now, now),
            )
            self._store.db.execute(
                "INSERT INTO project_memberships(project_id, principal_id, role, status, "
                "revision, granted_by, created_at, updated_at) VALUES (?, ?, ?, 'active', "
                "1, ?, ?, ?) ON CONFLICT(project_id, principal_id) DO UPDATE SET "
                "role=excluded.role, status='active', revision=project_memberships.revision + 1, "
                "granted_by=excluded.granted_by, updated_at=excluded.updated_at",
                (project_id, principal_id, role, actor_id, now, now),
            )
            self._store.db.commit()
        except Exception:
            self._store.db.rollback()
            raise
        membership = self.membership(principal_id, project_id)
        assert membership is not None
        return membership

    def revoke_membership(
        self, actor_id: str, project_id: str, principal_id: str
    ) -> None:
        if not self.can_access(actor_id, project_id, "admin"):
            raise MemoryAccessError("project membership operation is not permitted")
        self._store.db.execute("BEGIN IMMEDIATE")
        try:
            target = self.membership(principal_id, project_id)
            if target is None:
                raise MemoryAccessError("project membership does not exist")
            if target.role == "admin":
                count = self._store.db.execute(
                    "SELECT COUNT(*) FROM project_memberships WHERE project_id = ? "
                    "AND role = 'admin' AND status = 'active'",
                    (project_id,),
                ).fetchone()[0]
                if count <= 1:
                    raise MemoryAccessError("cannot remove the last project admin")
            self._store.db.execute(
                "UPDATE project_memberships SET status='revoked', "
                "revision=revision + 1, updated_at=? WHERE project_id=? "
                "AND principal_id=? AND status='active'",
                (time.time(), project_id, principal_id),
            )
            self._store.db.commit()
        except Exception:
            self._store.db.rollback()
            raise


class ProjectMemoryService:
    """Apply project role checks to project-audience Memory operations."""

    def __init__(
        self,
        store: MemoryStore,
        policy: ProjectAccessPolicy,
        *,
        principal_id: str,
        project_id: str,
    ) -> None:
        self.policy = policy
        self.principal_id = principal_id
        self.project_id = project_id
        self.scoped = ScopedMemoryStore(
            store,
            MemoryAccessContext(
                principal_id=principal_id,
                project_id=project_id,
                authenticated=True,
                readable_audiences=(("project", project_id),),
            ),
        )

    def records(self) -> list[dict[str, Any]]:
        self.policy.require_access(self.principal_id, self.project_id, "viewer")
        return self.scoped.records()

    def append(self, note: str) -> dict[str, Any]:
        self.policy.require_access(self.principal_id, self.project_id, "editor")
        return self.scoped.append_audience("project", self.project_id, note)

    def update(
        self, memory_id: str, note: str, *, expected_revision: int
    ) -> dict[str, Any]:
        self.policy.require_access(self.principal_id, self.project_id, "editor")
        return self.scoped.update_audience(
            memory_id, note, expected_revision=expected_revision
        )

    def forget(self, memory_id: str, *, expected_revision: int) -> None:
        self.policy.require_access(self.principal_id, self.project_id, "editor")
        self.scoped.forget_audience(memory_id, expected_revision=expected_revision)


__all__ = [
    "PROJECT_ROLES",
    "ProjectAccessPolicy",
    "ProjectMembership",
    "ProjectMemoryService",
]

"""Trusted Room membership and shared-memory authorization boundary."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from uuid import uuid4

from ..env_utils import env_get
from .memory_access import MemoryAccessContext, MemoryAccessError, ScopedMemoryStore
from .memory_store import MemoryStore

ROOM_ROLES = ("admin", "editor", "member")


def configured_admin_principals() -> frozenset[str]:
    """Return server-configured administrators; browser input is never used."""
    values = str(env_get("UAGENT_ADMIN_PRINCIPALS", "") or "").split(",")
    principals = {value.strip() for value in values if value.strip()}
    principals.add("local")
    return frozenset(principals)


@dataclass(frozen=True)
class RoomMembership:
    room_id: str
    principal_id: str
    role: str
    revision: int


class RoomAccessPolicy:
    """SQLite-backed policy; callers supply an authenticated principal."""

    def __init__(
        self, store: MemoryStore, *, admin_principals: frozenset[str] | None = None
    ):
        self._store = store
        self._admins = admin_principals or configured_admin_principals()

    def is_global_admin(self, principal_id: str) -> bool:
        return bool(principal_id and principal_id in self._admins)

    def membership(self, principal_id: str, room_id: str) -> RoomMembership | None:
        row = self._store.db.execute(
            "SELECT room_id, principal_id, role, revision FROM room_memberships "
            "WHERE room_id = ? AND principal_id = ? AND status = 'active'",
            (room_id, principal_id),
        ).fetchone()
        return RoomMembership(**dict(row)) if row is not None else None

    def private_room_owner(self, room_id: str) -> str | None:
        row = self._store.db.execute(
            "SELECT principal_id FROM private_rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
        return str(row["principal_id"]) if row is not None else None

    def private_room_session_id(self, room_id: str) -> str:
        row = self._store.db.execute(
            "SELECT session_id FROM private_rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
        return str(row["session_id"] or "") if row is not None else ""

    def is_private_room_for(self, principal_id: str, room_id: str) -> bool:
        owner = self.private_room_owner(room_id)
        if owner is None or owner != principal_id:
            return False
        rows = self._store.db.execute(
            "SELECT principal_id FROM room_memberships "
            "WHERE room_id = ? AND status = 'active'",
            (room_id,),
        ).fetchall()
        return len(rows) == 1 and str(rows[0]["principal_id"]) == owner

    def create_private_room(
        self,
        principal_id: str,
        room_id: str,
        *,
        project_id: str = "",
        session_id: str = "",
    ) -> None:
        """Create an opaque room whose only recipient is its authenticated owner."""
        principal_id = str(principal_id or "").strip()
        room_id = str(room_id or "").strip()
        project_id = str(project_id or "").strip()
        session_id = str(session_id or "").strip() or uuid4().hex
        if not principal_id or not room_id:
            raise ValueError("principal_id and room_id are required")
        if self._store.db.in_transaction:
            raise RuntimeError("private room creation requires its own transaction")
        now = time.time()
        self._store.db.execute("BEGIN IMMEDIATE")
        try:
            if project_id:
                from .project_access import ProjectAccessPolicy

                self._store.db.execute(
                    "INSERT OR IGNORE INTO projects(project_id, status, created_at, updated_at) "
                    "VALUES (?, 'active', ?, ?)",
                    (project_id, now, now),
                )
                if principal_id == "local":
                    # Local mode is a single-user trust boundary. Grant editor access
                    # only to this workspace so private Memory CRUD works.
                    self._store.db.execute(
                        "INSERT INTO project_memberships("
                        "project_id, principal_id, role, status, revision, granted_by, "
                        "created_at, updated_at) VALUES (?, 'local', 'editor', 'active', "
                        "1, 'local-private-session', ?, ?) "
                        "ON CONFLICT(project_id, principal_id) DO UPDATE SET "
                        "role=CASE WHEN project_memberships.role='admin' THEN 'admin' "
                        "ELSE 'editor' END, status='active', "
                        "revision=project_memberships.revision + 1, "
                        "granted_by='local-private-session', updated_at=excluded.updated_at",
                        (project_id, now, now),
                    )
                project_policy = ProjectAccessPolicy(self._store)
                project_policy.require_access(principal_id, project_id, "viewer")
                self._store.db.execute(
                    "INSERT INTO room_projects(room_id, project_id, revision, bound_by, "
                    "created_at, updated_at) VALUES (?, ?, 1, ?, ?, ?)",
                    (room_id, project_id, principal_id, now, now),
                )
            self._store.db.execute(
                "INSERT INTO private_rooms(room_id, principal_id, session_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (room_id, principal_id, session_id, now),
            )
            self._store.db.execute(
                "INSERT INTO room_memberships(room_id, principal_id, role, status, "
                "granted_by, created_at, updated_at) "
                "VALUES (?, ?, 'admin', 'active', ?, ?, ?)",
                (room_id, principal_id, principal_id, now, now),
            )
            self._store.db.commit()
        except Exception:
            self._store.db.rollback()
            raise

    def can_join(self, principal_id: str, room_id: str) -> bool:
        return self.membership(principal_id, room_id) is not None

    def can_read_room_memory(self, principal_id: str, room_id: str) -> bool:
        return self.can_join(principal_id, room_id)

    def can_write_room_memory(self, principal_id: str, room_id: str) -> bool:
        membership = self.membership(principal_id, room_id)
        return membership is not None and membership.role in {"admin", "editor"}

    def can_delete_room_memory(
        self, principal_id: str, room_id: str, memory_id: str
    ) -> bool:
        membership = self.membership(principal_id, room_id)
        if membership is None:
            return False
        if membership.role == "admin":
            return True
        row = self._store.db.execute(
            "SELECT owner_id FROM memories WHERE memory_id = ? "
            "AND audience_type = 'room' AND audience_id = ? AND status = 'active'",
            (memory_id, room_id),
        ).fetchone()
        return (
            membership.role == "editor"
            and row is not None
            and str(row["owner_id"] or "") == principal_id
        )

    def can_manage_members(self, principal_id: str, room_id: str) -> bool:
        membership = self.membership(principal_id, room_id)
        return self.is_global_admin(principal_id) or (
            membership is not None and membership.role == "admin"
        )

    def list_members(self, actor_id: str, room_id: str) -> list[dict[str, Any]]:
        if not self.can_manage_members(actor_id, room_id):
            raise MemoryAccessError("room membership operation is not permitted")
        rows = self._store.db.execute(
            "SELECT room_id, principal_id, role, revision FROM room_memberships "
            "WHERE room_id = ? AND status = 'active' ORDER BY principal_id",
            (room_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def set_membership(
        self, actor_id: str, room_id: str, principal_id: str, role: str
    ) -> RoomMembership:
        room_id = str(room_id or "").strip()
        principal_id = str(principal_id or "").strip()
        role = str(role or "").strip().lower()
        if not room_id or not principal_id or role not in ROOM_ROLES:
            raise ValueError("room_id, principal_id, and a valid role are required")
        private_owner = self.private_room_owner(room_id)
        if private_owner is not None and (
            actor_id != private_owner or principal_id != private_owner
        ):
            raise MemoryAccessError("private room membership is immutable")
        if not self.can_manage_members(actor_id, room_id):
            raise MemoryAccessError("room membership operation is not permitted")
        now = time.time()
        self._store.db.execute("BEGIN IMMEDIATE")
        try:
            self._store.db.execute(
                "INSERT INTO room_memberships(room_id, principal_id, role, status, "
                "granted_by, created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', ?, ?, ?) "
                "ON CONFLICT(room_id, principal_id) DO UPDATE SET "
                "role=excluded.role, status='active', "
                "revision=room_memberships.revision + 1, "
                "granted_by=excluded.granted_by, updated_at=excluded.updated_at",
                (room_id, principal_id, role, actor_id, now, now),
            )
            self._store.db.commit()
        except Exception:
            self._store.db.rollback()
            raise
        membership = self.membership(principal_id, room_id)
        assert membership is not None
        return membership

    def revoke_membership(self, actor_id: str, room_id: str, principal_id: str) -> None:
        if self.private_room_owner(room_id) is not None:
            raise MemoryAccessError("private room membership is immutable")
        if not self.can_manage_members(actor_id, room_id):
            raise MemoryAccessError("room membership operation is not permitted")
        self._store.db.execute("BEGIN IMMEDIATE")
        try:
            target = self.membership(principal_id, room_id)
            if target is None:
                raise MemoryAccessError("room membership does not exist")
            if target.role == "admin":
                count = self._store.db.execute(
                    "SELECT COUNT(*) FROM room_memberships WHERE room_id = ? "
                    "AND role = 'admin' AND status = 'active'",
                    (room_id,),
                ).fetchone()[0]
                if count <= 1:
                    raise MemoryAccessError("cannot remove the last room admin")
            self._store.db.execute(
                "UPDATE room_memberships SET status='revoked', "
                "revision=revision + 1, updated_at=? "
                "WHERE room_id=? AND principal_id=?",
                (time.time(), room_id, principal_id),
            )
            self._store.db.commit()
        except Exception:
            self._store.db.rollback()
            raise


class RoomMemoryService:
    """Combine room policy checks with audience-scoped store operations."""

    def __init__(
        self,
        store: MemoryStore,
        policy: RoomAccessPolicy,
        *,
        principal_id: str,
        project_id: str,
        room_id: str,
    ):
        self.policy = policy
        self.principal_id = principal_id
        self.room_id = room_id
        self.scoped = ScopedMemoryStore(
            store,
            MemoryAccessContext(
                principal_id=principal_id,
                project_id=project_id,
                room_id=room_id,
                authenticated=True,
                readable_audiences=(("room", room_id),),
            ),
        )

    def records(self) -> list[dict[str, Any]]:
        if not self.policy.can_read_room_memory(self.principal_id, self.room_id):
            raise MemoryAccessError("room memory read is not permitted")
        return self.scoped.records()

    def append(self, note: str) -> dict[str, Any]:
        if not self.policy.can_write_room_memory(self.principal_id, self.room_id):
            raise MemoryAccessError("room memory write is not permitted")
        return self.scoped.append_audience("room", self.room_id, note)

    def update(
        self, memory_id: str, note: str, *, expected_revision: int
    ) -> dict[str, Any]:
        if not self.policy.can_write_room_memory(self.principal_id, self.room_id):
            raise MemoryAccessError("room memory write is not permitted")
        return self.scoped.update_audience(
            memory_id, note, expected_revision=expected_revision
        )

    def forget(self, memory_id: str, *, expected_revision: int) -> None:
        if not self.policy.can_delete_room_memory(
            self.principal_id, self.room_id, memory_id
        ):
            raise MemoryAccessError("room memory delete is not permitted")
        self.scoped.forget_audience(memory_id, expected_revision=expected_revision)


__all__ = [
    "ROOM_ROLES",
    "RoomAccessPolicy",
    "RoomMembership",
    "RoomMemoryService",
    "configured_admin_principals",
]

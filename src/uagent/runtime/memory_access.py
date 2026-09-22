"""V3 store boundary for personal memory and explicit, revision-bound sharing.

This is a server-internal API. Context and authorized audiences come from trusted
identity/session/policy adapters, never from a browser or model payload. Legacy
MemoryStore methods remain available for local compatibility and migration only.
Web, projection and profile integration are separate rollout steps.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import time
from typing import Any, Iterator
import uuid

from .identity_context import TurnContext
from .memory_store import MemoryStore, MemoryStoreConflictError


class MemoryAccessError(PermissionError):
    """The requested operation is not available to this principal."""


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


@dataclass(frozen=True)
class MemoryAccessContext:
    """Resolved identity and output audience for one server-authorized operation.

    private_session must be explicitly enabled after verifying that the output
    and history are private to this principal. Otherwise personal records,
    including the principal's own records, are excluded from reads.
    """

    principal_id: str
    project_id: str
    authenticated: bool
    room_id: str = ""
    private_session: bool = False
    readable_audiences: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.authenticated is not True:
            raise MemoryAccessError("authenticated identity is required")
        for name in ("principal_id", "project_id"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name))
        if not isinstance(self.room_id, str):
            raise ValueError("room_id must be a string")
        if type(self.private_session) is not bool:
            raise ValueError("private_session must be a boolean")
        object.__setattr__(self, "room_id", self.room_id.strip())
        audiences = []
        for kind, audience_id in self.readable_audiences:
            if kind == "room" and self.room_id and audience_id == self.room_id:
                audiences.append((kind, audience_id))
            elif kind == "project" and audience_id == self.project_id:
                audiences.append((kind, audience_id))
            elif kind == "global" and audience_id == "":
                audiences.append((kind, audience_id))
            else:
                raise MemoryAccessError("invalid authorized audience")
        object.__setattr__(self, "readable_audiences", tuple(sorted(set(audiences))))

    @classmethod
    def from_turn(
        cls,
        turn: TurnContext,
        *,
        private_session: bool = False,
        readable_audiences: tuple[tuple[str, str], ...] = (),
    ) -> MemoryAccessContext:
        return cls(
            principal_id=turn.principal_id,
            project_id=turn.project_id,
            room_id=turn.room_id,
            authenticated=turn.authenticated,
            private_session=private_session,
            readable_audiences=readable_audiences,
        )


@contextmanager
def _write(store: MemoryStore) -> Iterator[None]:
    if store.db.in_transaction:
        raise RuntimeError("memory access operation requires its own transaction")
    store.db.execute("BEGIN IMMEDIATE")
    try:
        yield
        store.db.commit()
    except Exception:
        store.db.rollback()
        raise


class ScopedMemoryStore:
    """Access-controlled operations on the existing SQLite memory database."""

    def __init__(self, store: MemoryStore, context: MemoryAccessContext):
        if not isinstance(context, MemoryAccessContext):
            raise TypeError("resolved MemoryAccessContext is required")
        self._store = store
        self.context = context

    @property
    def access_generation(self) -> int:
        """Generation for future snapshot/continuation invalidation adapters."""
        row = self._store.db.execute(
            "SELECT value FROM memory_metadata WHERE key = 'access_generation'"
        ).fetchone()
        return int(row["value"])

    def _read_filter(self) -> tuple[str, list[Any]]:
        context = self.context
        clauses = []
        params: list[Any] = [context.project_id]
        if context.private_session:
            clauses.append(
                "(m.audience_type = 'personal' AND m.owner_id <> '' "
                "AND m.audience_id = m.owner_id AND (m.owner_id = ? OR EXISTS ("
                "SELECT 1 FROM memory_grants g WHERE g.memory_id = m.memory_id "
                "AND g.memory_revision = m.revision "
                "AND g.grantee_principal_id = ? AND g.granted_by = m.owner_id "
                "AND g.permission = 'read' AND g.status = 'active')))"
            )
            params.extend([context.principal_id, context.principal_id])
        for kind, audience_id in context.readable_audiences:
            clauses.append("(m.audience_type = ? AND m.audience_id = ?)")
            params.extend([kind, audience_id])
        return (
            "m.status = 'active' AND m.project = ? AND ("
            + (" OR ".join(clauses) or "0")
            + ")",
            params,
        )

    def _query(
        self, *, memory_id: str | None = None, query: str = "", count: bool = False
    ) -> Any:
        where, params = self._read_filter()
        if memory_id is not None:
            where += " AND m.memory_id = ?"
            params.append(memory_id)
        if query:
            where += " AND instr(lower(m.note), lower(?)) > 0"
            params.append(query)
        columns = "COUNT(*)"
        if not count:
            columns = (
                "m.*, (SELECT g.grant_id FROM memory_grants g "
                "WHERE g.memory_id = m.memory_id AND g.memory_revision = m.revision "
                "AND g.grantee_principal_id = ? AND g.granted_by = m.owner_id "
                "AND g.permission = 'read' AND g.status = 'active') AS read_grant_id"
            )
            params.insert(0, self.context.principal_id)
        rows = self._store.db.execute(
            f"SELECT {columns} FROM memories m WHERE {where} ORDER BY m.id", params
        ).fetchall()
        if count:
            return int(rows[0][0])
        result = []
        for row in rows:
            record = dict(row)
            record["ts"] = record["created_at"]
            record["shared_reference"] = (
                record["audience_type"] == "personal"
                and record["owner_id"] != self.context.principal_id
            )
            # A receiver never gets private source paths, actor claims, or the
            # owner's unrelated supersedes/source record identifiers.
            if record["shared_reference"]:
                for field in ("id", "owner", "source", "source_id", "supersedes_id"):
                    record.pop(field, None)
            result.append(record)
        return result

    def records(self, *, query: str = "") -> list[dict[str, Any]]:
        """Filter permission and project in SQL, before returning candidates."""
        return self._query(query=query)

    def get(self, memory_id: str) -> dict[str, Any] | None:
        rows = self._query(memory_id=memory_id)
        return rows[0] if rows else None

    def count(self, *, query: str = "") -> int:
        return self._query(query=query, count=True)

    def export(self) -> list[dict[str, Any]]:
        """Export exactly the currently readable records, retaining provenance."""
        return self.records()

    def _require_private(self) -> None:
        if not self.context.private_session:
            raise MemoryAccessError("personal operations require a private session")

    def append(self, note: str) -> dict[str, Any]:
        self._require_private()
        if not isinstance(note, str) or not note.strip():
            raise ValueError("note must not be empty")
        memory_id = uuid.uuid4().hex
        now = time.time()
        with _write(self._store):
            self._store.db.execute(
                "INSERT INTO memories(memory_id, created_at, updated_at, note, "
                "owner, owner_id, project, audience_type, audience_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'personal', ?)",
                (
                    memory_id,
                    now,
                    now,
                    note,
                    self.context.principal_id,
                    self.context.principal_id,
                    self.context.project_id,
                    self.context.principal_id,
                ),
            )
            return self.get(memory_id)

    def _owned(self, memory_id: str) -> dict[str, Any]:
        self._require_private()
        row = self._store.db.execute(
            "SELECT * FROM memories WHERE memory_id = ? AND owner_id = ? "
            "AND project = ? AND audience_type = 'personal' "
            "AND audience_id = owner_id AND status = 'active'",
            (memory_id, self.context.principal_id, self.context.project_id),
        ).fetchone()
        if row is None:
            raise MemoryAccessError("memory operation is not permitted")
        return dict(row)

    @staticmethod
    def _check_revision(record: dict[str, Any], expected_revision: int) -> None:
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        if record["revision"] != expected_revision:
            raise MemoryStoreConflictError("memory revision conflict")

    def update(
        self, memory_id: str, note: str, *, expected_revision: int
    ) -> dict[str, Any]:
        if not isinstance(note, str) or not note.strip():
            raise ValueError("note must not be empty")
        with _write(self._store):
            current = self._owned(memory_id)
            self._check_revision(current, expected_revision)
            self._store.db.execute(
                "UPDATE memories SET note = ?, revision = revision + 1, "
                "updated_at = ? WHERE memory_id = ?",
                (note, time.time(), memory_id),
            )
            return self.get(memory_id)

    def forget(self, memory_id: str, *, expected_revision: int) -> None:
        with _write(self._store):
            self._check_revision(self._owned(memory_id), expected_revision)
            self._store.db.execute(
                "DELETE FROM memories WHERE memory_id = ?", (memory_id,)
            )

    def share(
        self, memory_id: str, grantee_principal_id: str, *, expected_revision: int
    ) -> str:
        """Grant read-only access to precisely the owner's confirmed revision."""
        grantee = _identifier(grantee_principal_id, "grantee_principal_id")
        if grantee == self.context.principal_id:
            raise ValueError("self-sharing is not required")
        with _write(self._store):
            self._check_revision(self._owned(memory_id), expected_revision)
            existing = self._store.db.execute(
                "SELECT grant_id FROM memory_grants WHERE memory_id = ? "
                "AND memory_revision = ? AND grantee_principal_id = ? "
                "AND status = 'active'",
                (memory_id, expected_revision, grantee),
            ).fetchone()
            if existing is not None:
                return str(existing["grant_id"])
            grant_id = uuid.uuid4().hex
            self._store.db.execute(
                "INSERT INTO memory_grants(grant_id, memory_id, memory_revision, "
                "grantee_principal_id, permission, granted_by, status, created_at) "
                "VALUES (?, ?, ?, ?, 'read', ?, 'active', ?)",
                (
                    grant_id,
                    memory_id,
                    expected_revision,
                    grantee,
                    self.context.principal_id,
                    time.time(),
                ),
            )
        return grant_id

    def revoke(self, memory_id: str, grant_id: str) -> None:
        with _write(self._store):
            self._owned(memory_id)
            row = self._store.db.execute(
                "SELECT status FROM memory_grants WHERE grant_id = ? "
                "AND memory_id = ? AND granted_by = ?",
                (grant_id, memory_id, self.context.principal_id),
            ).fetchone()
            if row is None:
                raise MemoryAccessError("grant operation is not permitted")
            self._store.db.execute(
                "UPDATE memory_grants SET status = 'revoked', "
                "revision = revision + 1, revoked_at = ? "
                "WHERE grant_id = ? AND status = 'active'",
                (time.time(), grant_id),
            )


def map_legacy_owner(
    store: MemoryStore, *, legacy_owner: str, principal_id: str, project_id: str
) -> int:
    """Explicit trusted migration, after an administrator verifies the mapping.

    Never expose this function as a normal user/tool operation. It does not
    infer identity from an OS login, copy records, or create sharing grants.
    Empty/unknown legacy owners remain quarantined from scoped reads.
    """
    legacy_owner = _identifier(legacy_owner, "legacy_owner")
    principal_id = _identifier(principal_id, "principal_id")
    project_id = _identifier(project_id, "project_id")
    with _write(store):
        cursor = store.db.execute(
            "UPDATE memories SET owner_id = ?, audience_type = 'personal', "
            "audience_id = ?, revision = revision + 1, updated_at = ? "
            "WHERE owner = ? AND project = ? AND audience_type = 'legacy' "
            "AND (owner_id IS NULL OR owner_id = '')",
            (principal_id, principal_id, time.time(), legacy_owner, project_id),
        )
        return cursor.rowcount

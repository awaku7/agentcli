"""Connection-local principal boundary for WebSocket turns."""

from __future__ import annotations

from dataclasses import dataclass

from ..runtime.identity_context import (
    IdentityContext,
    IdentityResolutionError,
    TurnContext,
    resolve_turn_context,
)
from ..runtime.session_store import project_id_from_path


@dataclass(frozen=True)
class WebConnectionContext:
    """Trusted identity captured at connection acceptance, never from a message."""

    room_id: str
    identity: IdentityContext
    configuration_fingerprint: str = ""
    project_id: str = ""
    private_session: bool = False
    session_id: str = ""

    def validate_authentication_configuration(self) -> None:
        """Reject every message from a connection bound to stale authentication."""
        if self.configuration_fingerprint:
            from ..runtime.auth_management import (
                authentication_configuration_fingerprint,
            )

            if (
                self.configuration_fingerprint
                != authentication_configuration_fingerprint()
            ):
                raise IdentityResolutionError("authentication configuration changed")

    def make_turn(self, *, project_path: str, session_id: str) -> TurnContext:
        self.validate_authentication_configuration()
        return TurnContext.from_identity(
            self.identity,
            room_id=self.room_id,
            project_id=self.project_id or project_id_from_path(project_path),
            session_id=self.session_id or session_id,
            entry_point="web",
            private_session=self.private_session,
            server_bound_project=bool(self.project_id),
        )

    def validate_room_access(self) -> None:
        """Re-check recipient authorization before delivering room broadcasts."""
        try:
            project_id, private_session = require_room_access(
                self.identity, self.room_id
            )
            if private_session != self.private_session:
                raise IdentityResolutionError("private room binding changed")
            if self.project_id and project_id != self.project_id:
                raise IdentityResolutionError("room project binding changed")
        except IdentityResolutionError:
            raise
        except Exception as exc:
            raise IdentityResolutionError(
                "room or project access is unavailable"
            ) from exc


def require_room_access(identity: IdentityContext, room_id: str) -> tuple[str, bool]:
    """Authorize one recipient against the current room and project policies."""
    from ..runtime.memory_store import open_memory_store
    from ..runtime.project_access import ProjectAccessPolicy
    from ..runtime.room_access import RoomAccessPolicy
    from ..tools import long_memory

    if not identity.authenticated:
        raise IdentityResolutionError("authenticated identity is required")
    if not long_memory.is_sqlite_backend():
        raise IdentityResolutionError("multi-user rooms require SQLite memory")
    store = open_memory_store(long_memory._sqlite_path())
    try:
        room_policy = RoomAccessPolicy(store)
        private_owner = room_policy.private_room_owner(room_id)
        private_session = private_owner is not None
        if private_session:
            if not room_policy.is_private_room_for(identity.principal_id, room_id):
                raise IdentityResolutionError("private room audience is not authorized")
        elif room_policy.membership(identity.principal_id, room_id) is None:
            if identity.authn_kind == "local":
                room_policy.set_membership(
                    identity.principal_id, room_id, identity.principal_id, "admin"
                )
            else:
                raise IdentityResolutionError("room membership is no longer active")
        project_policy = ProjectAccessPolicy(store)
        project_id = project_policy.room_project(room_id) or ""
        if project_id:
            project_policy.sync_directory_policy(identity)
            project_policy.require_access(identity.principal_id, project_id, "viewer")
        return project_id, private_session
    finally:
        store.close()


def resolve_web_connection(websocket: object, room_id: str) -> WebConnectionContext:
    """Resolve the selected identity mode before joining a room."""
    from ..runtime.auth_management import authentication_configuration_fingerprint

    configuration_fingerprint = authentication_configuration_fingerprint()
    identity, _ = resolve_turn_context(
        entry_point="web", room_id=room_id, request_context=websocket
    )
    if not identity.authenticated:
        raise IdentityResolutionError("unauthenticated Web connection")
    from ..runtime.memory_store import open_memory_store
    from ..runtime.room_access import RoomAccessPolicy
    from ..tools import long_memory

    if not long_memory.is_sqlite_backend():
        raise IdentityResolutionError("multi-user rooms require SQLite memory")
    store = open_memory_store(long_memory._sqlite_path())
    try:
        policy = RoomAccessPolicy(store)
        private_owner = policy.private_room_owner(room_id)
        private_session = private_owner is not None
        if private_session:
            if not policy.is_private_room_for(identity.principal_id, room_id):
                raise IdentityResolutionError("private room access is not permitted")
        else:
            membership = policy.membership(identity.principal_id, room_id)
            if membership is None and identity.authn_kind == "local":
                policy.set_membership(
                    identity.principal_id, room_id, identity.principal_id, "admin"
                )
            elif membership is None:
                raise IdentityResolutionError("room membership is required")
        private_session_id = (
            policy.private_room_session_id(room_id) if private_session else ""
        )
        from ..runtime.project_access import ProjectAccessPolicy

        project_id = ProjectAccessPolicy(store).room_project(room_id) or ""
    finally:
        store.close()
    if configuration_fingerprint != authentication_configuration_fingerprint():
        raise IdentityResolutionError("authentication configuration changed")

    connection = WebConnectionContext(
        room_id=room_id,
        identity=identity,
        configuration_fingerprint=configuration_fingerprint,
        project_id=project_id,
        private_session=private_session,
        session_id=private_session_id,
    )
    connection.validate_room_access()
    return connection

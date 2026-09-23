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
            project_id=project_id_from_path(project_path),
            session_id=session_id,
            entry_point="web",
        )


def resolve_web_connection(websocket: object, room_id: str) -> WebConnectionContext:
    """Resolve the selected identity mode before joining a room."""
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
        membership = policy.membership(identity.principal_id, room_id)
        if membership is None and identity.authn_kind == "local":
            policy.set_membership(
                identity.principal_id, room_id, identity.principal_id, "admin"
            )
        elif membership is None:
            raise IdentityResolutionError("room membership is required")
    finally:
        store.close()
    from ..runtime.auth_management import authentication_configuration_fingerprint

    return WebConnectionContext(
        room_id=room_id,
        identity=identity,
        configuration_fingerprint=authentication_configuration_fingerprint(),
    )

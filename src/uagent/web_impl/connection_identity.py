"""Connection-local principal boundary for WebSocket turns."""

from __future__ import annotations

from dataclasses import dataclass

from ..runtime.identity_context import (
    IdentityContext,
    TurnContext,
    resolve_turn_context,
)
from ..runtime.session_store import project_id_from_path


@dataclass(frozen=True)
class WebConnectionContext:
    """Trusted identity captured at connection acceptance, never from a message."""

    room_id: str
    identity: IdentityContext

    def make_turn(self, *, project_path: str, session_id: str) -> TurnContext:
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
        from ..runtime.identity_context import IdentityResolutionError

        raise IdentityResolutionError("unauthenticated Web connection")
    return WebConnectionContext(room_id=room_id, identity=identity)

from __future__ import annotations

import pytest

from uagent.auth.oidc_sessions import OIDCSessionStore
from uagent.runtime.identity_context import IdentityContext, IdentityResolutionError
from uagent.web_impl import connection_identity


def test_oidc_web_turn_revalidates_server_side_session(monkeypatch, tmp_path) -> None:
    identity = IdentityContext("user-A", True, "oidc")
    store = OIDCSessionStore(configuration_fingerprint=lambda: "revision-1")
    token = store.create(identity)
    monkeypatch.setattr(
        "uagent.auth.oidc_sessions.get_oidc_session_store", lambda: store
    )
    monkeypatch.setattr(
        connection_identity,
        "require_room_access",
        lambda current, room_id, *, touch_activity=True: ("", False),
    )

    connection = connection_identity.WebConnectionContext(
        room_id="shared",
        identity=identity,
        oidc_session_token=token,
    )
    turn = connection.make_turn(
        project_path=str(tmp_path),
        session_id="session-1",
    )
    assert turn.principal_id == "user-A"
    assert token not in repr(connection)

    store.revoke(token)
    with pytest.raises(IdentityResolutionError, match="invalid or expired"):
        connection.make_turn(
            project_path=str(tmp_path),
            session_id="session-2",
        )


def test_oidc_web_turn_without_server_side_handle_fails_closed(
    monkeypatch, tmp_path
) -> None:
    identity = IdentityContext("user-A", True, "oidc")
    monkeypatch.setattr(
        connection_identity,
        "require_room_access",
        lambda current, room_id, *, touch_activity=True: ("", False),
    )
    connection = connection_identity.WebConnectionContext(
        room_id="shared",
        identity=identity,
    )

    with pytest.raises(IdentityResolutionError, match="handle is missing"):
        connection.make_turn(
            project_path=str(tmp_path),
            session_id="session-1",
        )

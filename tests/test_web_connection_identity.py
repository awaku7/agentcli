"""Web connection identity must never be selected from room or message data."""

from __future__ import annotations

import pytest

from uagent.runtime.identity_context import (
    IdentityContext,
    IdentityResolutionError,
    call_with_turn_context,
    get_current_turn_context,
)
from uagent.web_impl import connection_identity


def test_same_room_connections_keep_distinct_principals(tmp_path, monkeypatch):
    def resolve(*, request_context, **kwargs):
        del kwargs
        identity = IdentityContext(request_context, True, "test")
        return identity, None

    monkeypatch.setattr(connection_identity, "resolve_turn_context", resolve)
    a = connection_identity.resolve_web_connection("user-A", "shared")
    b = connection_identity.resolve_web_connection("user-B", "shared")
    turn_a = a.make_turn(project_path=str(tmp_path), session_id="session-1")
    turn_b = b.make_turn(project_path=str(tmp_path), session_id="session-1")

    assert turn_a.room_id == turn_b.room_id == "shared"
    assert turn_a.principal_id == "user-A"
    assert turn_b.principal_id == "user-B"
    assert (
        call_with_turn_context(
            turn_a, get_current_turn_context, identity_context=a.identity
        )
        == turn_a
    )
    assert (
        call_with_turn_context(
            turn_b, get_current_turn_context, identity_context=b.identity
        )
        == turn_b
    )
    assert get_current_turn_context() is None


def test_unresolved_web_connection_fails_closed(monkeypatch):
    def fail(**kwargs):
        raise IdentityResolutionError("invalid credentials")

    monkeypatch.setattr(connection_identity, "resolve_turn_context", fail)
    with pytest.raises(IdentityResolutionError):
        connection_identity.resolve_web_connection(object(), "shared")


def test_unauthenticated_web_connection_fails_closed(monkeypatch):
    monkeypatch.setattr(
        connection_identity,
        "resolve_turn_context",
        lambda **kwargs: (IdentityContext("anonymous", False, "test"), None),
    )
    with pytest.raises(IdentityResolutionError):
        connection_identity.resolve_web_connection(object(), "shared")


def test_websocket_worker_uses_connection_identity_not_message_owner():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "src/uagent/web_impl/routes_ws.py").read_text(encoding="utf-8")
    assert "resolve_web_connection(websocket, room_id)" in source
    assert source.count("connection.make_turn(") == 2
    assert source.count("identity_context=connection.identity") == 0
    assert source.count('"identity_context": connection.identity') == 2


def test_web_worker_rejects_identity_mismatch_before_side_effects(tmp_path):
    from types import SimpleNamespace

    from uagent.web_impl.agent_worker import run_agent_worker

    room = SimpleNamespace(room_id="shared")
    connection = connection_identity.WebConnectionContext(
        "shared", IdentityContext("user-A", True, "test")
    )
    turn = connection.make_turn(project_path=str(tmp_path), session_id="session-1")

    with pytest.raises(IdentityResolutionError, match="identity/turn mismatch"):
        run_agent_worker(
            room,
            "hello",
            turn_context=turn,
            identity_context=IdentityContext("user-B", True, "test"),
            project_path=str(tmp_path),
        )
    with pytest.raises(IdentityResolutionError, match="project mismatch"):
        run_agent_worker(
            room,
            "hello",
            turn_context=turn,
            identity_context=connection.identity,
            project_path=str(tmp_path / "other"),
        )


def test_web_worker_directory_is_captured_with_turn():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    routes = (root / "src/uagent/web_impl/routes_ws.py").read_text(encoding="utf-8")
    worker = (root / "src/uagent/web_impl/agent_worker.py").read_text(encoding="utf-8")
    assert routes.count("worker_dir = room.base_dir") == 2
    assert routes.count('"project_path": worker_dir') == 2
    assert routes.count("project_path=worker_dir") == 2
    expected = "os.chdir(project_path if turn_context is not None else room.base_dir)"
    assert expected in worker

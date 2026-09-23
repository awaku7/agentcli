"""Web connection identity must never be selected from room or message data."""

from __future__ import annotations

import asyncio
import pytest

from uagent.runtime.identity_context import (
    IdentityContext,
    IdentityResolutionError,
    call_with_turn_context,
    get_current_turn_context,
)
from uagent.web_impl import connection_identity


def test_same_room_connections_keep_distinct_principals(tmp_path, monkeypatch):
    from uagent.runtime.memory_store import MemoryStore
    from uagent.runtime.room_access import RoomAccessPolicy

    memory_path = tmp_path / "memory.sqlite3"
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(memory_path))
    store = MemoryStore(memory_path)
    policy = RoomAccessPolicy(store, admin_principals=frozenset({"root"}))
    policy.set_membership("root", "shared", "user-A", "member")
    policy.set_membership("root", "shared", "user-B", "member")
    store.close()

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
    validation = source.index("connection.validate_authentication_configuration()")
    assert validation < source.index('payload.get("type") == "user_input"')


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


def test_web_connection_rejects_turn_after_authentication_config_change(
    tmp_path, monkeypatch
):
    revision = ["revision-1"]
    monkeypatch.setattr(
        "uagent.runtime.auth_management.authentication_configuration_fingerprint",
        lambda: revision[0],
    )
    connection = connection_identity.WebConnectionContext(
        "shared",
        IdentityContext("user-A", True, "test"),
        configuration_fingerprint="revision-1",
    )

    revision[0] = "revision-2"
    with pytest.raises(IdentityResolutionError, match="configuration changed"):
        connection.make_turn(project_path=str(tmp_path), session_id="session-1")


def test_web_connection_rejects_configuration_change_during_resolution(
    tmp_path, monkeypatch
):
    from uagent.runtime.memory_store import MemoryStore

    memory_path = tmp_path / "memory.sqlite3"
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(memory_path))
    MemoryStore(memory_path).close()
    revisions = iter(("revision-1", "revision-2"))
    monkeypatch.setattr(
        "uagent.runtime.auth_management.authentication_configuration_fingerprint",
        lambda: next(revisions),
    )
    monkeypatch.setattr(
        connection_identity,
        "resolve_turn_context",
        lambda **kwargs: (IdentityContext("local", True, "local"), None),
    )

    with pytest.raises(IdentityResolutionError, match="configuration changed"):
        connection_identity.resolve_web_connection(object(), "shared")


def test_room_broadcast_closes_stale_authenticated_connection(monkeypatch):
    from uagent.web_impl.rooms import WebRoom

    revision = ["revision-1"]
    monkeypatch.setattr(
        "uagent.runtime.auth_management.authentication_configuration_fingerprint",
        lambda: revision[0],
    )

    class Socket:
        def __init__(self):
            self.sent = []
            self.closed = []

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self, code):
            self.closed.append(code)

    room = WebRoom("shared")
    socket = Socket()
    connection = connection_identity.WebConnectionContext(
        "shared",
        IdentityContext("user-A", True, "test"),
        configuration_fingerprint="revision-1",
    )
    room.active_connections.append(socket)
    room._connection_contexts[id(socket)] = connection

    revision[0] = "revision-2"
    asyncio.run(room.broadcast({"type": "message"}))

    assert socket.sent == []
    assert socket.closed == [1008]
    assert socket not in room.active_connections

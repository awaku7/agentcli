from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import WebSocketDisconnect
from fastapi.responses import JSONResponse

from uagent.runtime.identity_context import IdentityContext
from uagent.web_impl import io, routes_api, routes_ws
from uagent.web_impl.command_policy import web_command_denial
from uagent.web_impl.rooms import WebRoom, web_manager


@pytest.mark.parametrize(
    "command",
    [
        ":cp source destination",
        ":mv source destination",
        ":plugincmd:run",
        ":help",
    ],
)
@pytest.mark.parametrize(
    ("execution_profile", "sandbox_enabled"),
    [("remote", False), ("remote", True), ("local_trusted", True)],
)
@pytest.mark.parametrize("entrypoint", ["api", "websocket"])
def test_web_commands_fail_closed_before_host_dispatch(
    monkeypatch, command, execution_profile, sandbox_enabled, entrypoint
):
    calls = []
    monkeypatch.setattr(
        web_manager, "execution_profile", execution_profile, raising=False
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", sandbox_enabled, raising=False)
    monkeypatch.setattr(web_manager, "room_worker_pool", None, raising=False)
    monkeypatch.setattr(
        routes_api.tools_util,
        "handle_command",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        routes_ws.tools_util,
        "handle_command",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    from uagent import tools
    from uagent import util_cmd_files

    monkeypatch.setattr(
        tools,
        "handle_dynamic_command",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        util_cmd_files.shutil,
        "copy2",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        util_cmd_files.os,
        "replace",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    identity = IdentityContext("alice", True, "oidc")
    if entrypoint == "api":

        class Request:
            cookies = {}

            async def json(self):
                return {"room_id": "remote-room", "command": command}

        monkeypatch.setattr(routes_api, "_request_identity", lambda _request: identity)
        from uagent.web_impl import connection_identity

        monkeypatch.setattr(
            connection_identity,
            "require_room_access",
            lambda _identity, _room_id: ("project-a", False),
        )
        result = asyncio.run(routes_api.api_command(Request()))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 403
    else:
        room = WebRoom("remote-room")
        room.connect = _async_noop
        room.disconnect = lambda _socket: None
        monkeypatch.setattr(
            web_manager,
            "get_or_create_room",
            lambda _room_id: (room, False),
        )
        monkeypatch.setattr(routes_ws, "validate_websocket_origin", lambda _ws: None)
        monkeypatch.setattr(
            routes_ws,
            "trusted_ingress_carrier_for_request",
            lambda _ws: object(),
        )
        monkeypatch.setattr(
            routes_ws, "_bootstrap_room_on_connect", lambda _room, **_kwargs: None
        )

        class Connection:
            session_id = "session-a"
            private_session = False
            project_id = "project-a"

            def __init__(self):
                self.identity = identity

            def validate_authentication_configuration(self):
                return None

            def validate_room_access(self, *, touch_activity=True):
                return None

            def make_turn(self, **_kwargs):
                return None

        monkeypatch.setattr(
            routes_ws, "resolve_web_connection", lambda _ws, _room_id: Connection()
        )

        class Socket:
            query_params = {"room": "remote-room", "lang": "en"}

            def __init__(self):
                self.sent = False

            async def receive_text(self):
                if self.sent:
                    raise WebSocketDisconnect(code=1000)
                self.sent = True
                return json.dumps({"type": "command", "text": command})

            async def close(self, code=1000):
                return None

        asyncio.run(routes_ws.websocket_endpoint(Socket()))
        assert any("[DENIED]" in item.get("content", "") for item in room.messages)

    assert calls == []


async def _async_noop(*_args, **_kwargs):
    return None


@pytest.mark.parametrize("entrypoint", ["api", "websocket"])
def test_otel_command_does_not_initialize_llm_provider(
    monkeypatch, entrypoint, capsys
):
    """Status-only Web commands must not trigger provider auto-installation."""
    from uagent import util_tools
    from uagent.web_impl import connection_identity

    def unexpected_provider(*_args, **_kwargs):
        pytest.fail(":otel initialized the LLM provider")

    monkeypatch.setattr(routes_api.providers, "make_client", unexpected_provider)
    monkeypatch.setattr(routes_ws.providers, "make_client", unexpected_provider)
    monkeypatch.setattr(web_manager, "execution_profile", "remote", raising=False)
    monkeypatch.setattr(web_manager, "sandbox_enabled", True, raising=False)
    monkeypatch.setattr(web_manager, "room_worker_pool", None, raising=False)
    identity = IdentityContext("alice", True, "oidc")
    room = WebRoom("otel-room")
    if entrypoint == "api":
        monkeypatch.setattr(
            routes_api, "_request_identity", lambda _request: identity
        )
        monkeypatch.setattr(
            connection_identity,
            "require_room_access",
            lambda _identity, _room_id: ("project-a", False),
        )
        monkeypatch.setattr(web_manager, "get_room", lambda _room_id: room)

        class Request:
            cookies = {}

            async def json(self):
                return {"room_id": "otel-room", "command": ":otel"}

        result = asyncio.run(routes_api.api_command(Request()))
        assert isinstance(result, dict)
        assert result["ok"] is True
        assert result["run_llm"] is False
    else:
        room.connect = _async_noop
        room.disconnect = lambda _socket: None
        monkeypatch.setattr(
            web_manager, "get_or_create_room", lambda _room_id: (room, False)
        )
        monkeypatch.setattr(routes_ws, "validate_websocket_origin", lambda _ws: None)
        monkeypatch.setattr(
            routes_ws, "trusted_ingress_carrier_for_request", lambda _ws: object()
        )
        monkeypatch.setattr(
            routes_ws, "_bootstrap_room_on_connect", lambda _room, **_kwargs: None
        )

        class Connection:
            session_id = "session-a"
            private_session = False
            project_id = "project-a"
            identity = identity

            def validate_authentication_configuration(self):
                return None

            def validate_room_access(self, *, touch_activity=True):
                return None

            def make_turn(self, **_kwargs):
                pytest.fail(":otel started an LLM turn")

        monkeypatch.setattr(
            routes_ws, "resolve_web_connection", lambda _ws, _room_id: Connection()
        )

        class Socket:
            query_params = {"room": "otel-room", "lang": "en"}

            def __init__(self):
                self.sent = False

            async def receive_text(self):
                if self.sent:
                    raise WebSocketDisconnect(code=1000)
                self.sent = True
                return json.dumps({"type": "command", "text": ":otel"})

            async def close(self, code=1000):
                return None

        asyncio.run(routes_ws.websocket_endpoint(Socket()))

    assert any(
        item.get("role") == "assistant" and "OTel:" in item.get("content", "")
        for item in room.messages
    )


def test_websocket_rejects_input_until_startup_initialization_finishes(monkeypatch):
    room = WebRoom("initializing-room")
    room._bootstrap_started = True
    room.history_initialized = False
    room.messages = []
    room.add_message = room.messages.append

    async def connect(socket, _connection):
        room.active_connections.append(socket)

    room.connect = connect
    room.disconnect = lambda socket: room.active_connections.remove(socket)
    monkeypatch.setattr(
        web_manager, "get_or_create_room", lambda _room_id: (room, False)
    )
    monkeypatch.setattr(routes_ws, "validate_websocket_origin", lambda _ws: None)
    monkeypatch.setattr(
        routes_ws, "trusted_ingress_carrier_for_request", lambda _ws: None
    )
    monkeypatch.setattr(
        routes_ws, "_bootstrap_room_on_connect", lambda _room, **_kwargs: None
    )
    monkeypatch.setattr(
        routes_ws,
        "run_agent_worker",
        lambda *args, **kwargs: pytest.fail("worker started before init"),
    )

    class Connection:
        session_id = "session-a"
        private_session = False
        project_id = "project-a"
        identity = IdentityContext("alice", True, "oidc")

        def validate_authentication_configuration(self):
            return None

        def validate_room_access(self):
            return None

        def make_turn(self, **_kwargs):
            return None

    monkeypatch.setattr(
        routes_ws, "resolve_web_connection", lambda _ws, _room_id: Connection()
    )

    class Socket:
        query_params = {"room": "initializing-room", "lang": "en"}

        def __init__(self):
            self.received = False

        async def receive_text(self):
            if self.received:
                raise WebSocketDisconnect(code=1000)
            self.received = True
            return json.dumps({"type": "user_input", "text": "early message"})

        async def close(self, code=1000):
            return None

    asyncio.run(routes_ws.websocket_endpoint(Socket()))

    assert len(room.messages) == 1
    assert "initialization is still in progress" in room.messages[0]["content"]


def test_local_trusted_web_keeps_host_commands_when_sandbox_is_off():
    assert (
        web_command_denial(
            ":cp source destination",
            execution_profile="local_trusted",
            sandbox_enabled=False,
        )
        is None
    )


def test_sandboxed_or_remote_web_allows_only_mode_changes():
    for profile, sandbox_enabled in (
        ("remote", False),
        ("remote", True),
        ("local_trusted", True),
    ):
        for command in (
            ":r high",
            ":reasoning low",
            ":v high",
            ":verbosity low",
            ":otel",
        ):
            assert (
                web_command_denial(
                    command,
                    execution_profile=profile,
                    sandbox_enabled=sandbox_enabled,
                )
                is None
            )

        for command in (
            ":help",
            ":h tools",
            ":?",
            ":cp a b",
            ":mv a b",
            ":rm a",
            ":credential list",
            ":skills install x",
            ":plugin:run",
            ":otel --anything",
            ":unknown",
        ):
            assert web_command_denial(
                command,
                execution_profile=profile,
                sandbox_enabled=sandbox_enabled,
            )


def test_empty_human_ask_retry_preserves_private_authorization_metadata(monkeypatch):
    room = WebRoom("remote-room")
    room.loop = object()
    room.active_connections.append(object())
    room._web_parent_authorizes_connections = True
    broadcasts = []
    broadcast_lock = threading.Lock()

    async def broadcast(event):
        with broadcast_lock:
            broadcasts.append(dict(event))

    room.broadcast = broadcast

    class Completed:
        def result(self, timeout=None):
            return None

    def run_coroutine_threadsafe(coro, _loop):
        asyncio.run(coro)
        return Completed()

    monkeypatch.setattr(
        io.asyncio, "run_coroutine_threadsafe", run_coroutine_threadsafe
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(
            io.web_human_ask,
            room,
            {
                "message": "Approve?",
                "_job_id": "job-alice",
                "_expected_principal_id": "alice",
            },
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with broadcast_lock:
                if broadcasts:
                    break
            time.sleep(0.01)
        assert broadcasts

        room.human_ask_result = ""
        room.human_ask_sync_event.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with broadcast_lock:
                if len(broadcasts) >= 2:
                    break
            time.sleep(0.01)
        with broadcast_lock:
            assert len(broadcasts) >= 2
            initial, retry = broadcasts[:2]
        assert retry["_authorization_principal_id"] == "alice"
        assert retry["_authorization_job_id"] == "job-alice"

        from uagent.web_impl.process_workers import RoomWorkerPool

        parent_room = WebRoom("remote-room")
        parent_room.loop = object()
        parent_events = []

        async def parent_broadcast(event, *, _connections=None):
            parent_events.append(dict(event))

        parent_room.broadcast = parent_broadcast
        parent_room._pending_replays[1] = []
        for event in (initial, retry):
            RoomWorkerPool._relay(parent_room, event)
            assert parent_room._human_ask_expected_principal_id == "alice"
            assert parent_room.human_ask_job_id == "job-alice"
        assert len(parent_events) == 2
        assert all(
            "_authorization_principal_id" not in event
            and "_authorization_job_id" not in event
            for event in parent_events
        )
        assert all(
            "_authorization_principal_id" not in event
            and "_authorization_job_id" not in event
            for event in parent_room._pending_replays[1]
        )

        room.human_ask_result = "approved"
        room.human_ask_sync_event.set()
        assert json.loads(pending.result(timeout=3))["user_reply"] == "approved"

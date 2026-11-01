"""Web Sandbox status is scoped to the authorized room and live worker."""

import asyncio
import json
import threading
from types import SimpleNamespace

from fastapi.responses import JSONResponse

from uagent.runtime import mxc_backend
from uagent.runtime.execution_broker import TrustedSandboxScope
from uagent.web_impl import connection_identity, routes_api
from uagent.web_impl.rooms import WebRoom, web_manager


def _scope():
    return TrustedSandboxScope(
        deployment_id="web",
        principal_id="alice",
        project_id="project-a",
        scope_kind="web-room",
        scope_id="room-a",
        binding_generation="generation-a",
    )


def test_live_web_worker_checks_process_and_scope():
    scope = _scope()
    manager = object.__new__(mxc_backend.MxcSessionManager)
    manager._lock = threading.RLock()
    manager._active_web_scopes = {scope}
    process = SimpleNamespace(poll=lambda: None)
    session = SimpleNamespace(_closed=False, _proc=process, _mac_scope=None)
    manager._sessions = {mxc_backend._scope_key(scope): session}

    assert manager.has_live_web_worker(scope)
    process.poll = lambda: 1
    assert not manager.has_live_web_worker(scope)
    process.poll = lambda: None
    session._closed = True
    assert not manager.has_live_web_worker(scope)
    session._closed = False
    manager._active_web_scopes.clear()
    assert not manager.has_live_web_worker(scope)


def test_room_status_distinguishes_off_ready_running_and_unavailable(monkeypatch):
    room = WebRoom("room-a")
    scope = _scope()
    monkeypatch.setattr(web_manager, "rooms", {"room-a": room})
    monkeypatch.setattr(
        routes_api,
        "_request_identity",
        lambda _request: SimpleNamespace(principal_id="alice", authn_kind="oidc"),
    )
    monkeypatch.setattr(
        connection_identity,
        "require_room_access",
        lambda _identity, _room, **_kwargs: ("project-a", True),
    )
    manager = SimpleNamespace(has_live_web_worker=lambda active: active == scope)
    monkeypatch.setattr(web_manager, "sandbox_session_manager", manager)

    def get_state():
        response = asyncio.run(
            routes_api.get_room_sandbox_status(object(), "room-a")
        )
        assert isinstance(response, JSONResponse)
        assert response.headers["cache-control"] == "no-store"
        return json.loads(response.body)["state"]

    monkeypatch.setattr(web_manager, "sandbox_enabled", False)
    assert get_state() == "OFF"
    monkeypatch.setattr(web_manager, "sandbox_enabled", True)
    assert get_state() == "READY"
    room._sandbox_scope = scope
    assert get_state() == "RUNNING"
    monkeypatch.setattr(web_manager, "sandbox_session_manager", None)
    assert get_state() == "UNKNOWN"


def test_room_status_denies_unauthorized_users(monkeypatch):
    monkeypatch.setattr(
        routes_api,
        "_request_identity",
        lambda _request: SimpleNamespace(principal_id="eve"),
    )

    def reject(_identity, _room, **_kwargs):
        raise PermissionError("room access denied")

    monkeypatch.setattr(connection_identity, "require_room_access", reject)
    response = asyncio.run(
        routes_api.get_room_sandbox_status(object(), "room-a")
    )
    assert response.status_code == 403

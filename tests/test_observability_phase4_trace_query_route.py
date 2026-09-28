from __future__ import annotations

import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from uagent.runtime.identity_context import (
    IdentityContext,
    IdentityResolutionError,
)
from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.observability.noop import NOOP_BACKEND
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.observability.trace_ownership_index import TraceOwnershipIndex
from uagent.runtime.project_access import ProjectAccessPolicy
from uagent.runtime.room_access import RoomAccessPolicy
from uagent.web_impl.app import app
from uagent.web_impl import routes_observability

TRACE_ID = "1" * 32
ROOT_SPAN_ID = "2" * 16
CHILD_SPAN_ID = "3" * 16


def _settings(enabled: bool) -> ObservabilitySettings:
    return ObservabilitySettings(enabled=True, trace_query_enabled=enabled)


def _identity(principal_id: str = "alice") -> IdentityContext:
    return IdentityContext(principal_id, True, "oidc")


def _active_backend():
    return SimpleNamespace(enabled=True)


def _state_with_segment(
    *,
    principal_id: str = "alice",
    room_id: str = "",
    project_id: str = "",
    private_session: bool = False,
    server_bound_project: bool = False,
    with_child: bool = False,
):
    index = TraceOwnershipIndex()
    handle = index.admit_segment(
        trace_id=TRACE_ID,
        root_span_id=ROOT_SPAN_ID,
        principal_id=principal_id,
        room_id=room_id,
        project_id=project_id,
        service="uagent-test",
        entry_point="web",
        private_session=private_session,
        server_bound_project=server_bound_project,
    )
    assert handle is not None
    if with_child:
        assert index.register_span(
            handle,
            span_id=CHILD_SPAN_ID,
            semantic_kind="chat",
        )
    return routes_observability._TraceQueryIndexState(index=index, epoch=7)


def _enable_route(monkeypatch, *, principal_id: str = "alice") -> None:
    monkeypatch.setattr(
        routes_observability,
        "get_observability_settings",
        lambda: _settings(True),
    )
    monkeypatch.setattr(
        routes_observability,
        "get_observability_backend",
        _active_backend,
    )
    monkeypatch.setattr(
        routes_observability,
        "_request_identity",
        lambda request: _identity(principal_id),
    )


def _bind_state(monkeypatch, state) -> None:
    monkeypatch.setattr(routes_observability, "_query_index_state", lambda: state)
    monkeypatch.setattr(
        routes_observability,
        "_query_index_state_is_current",
        lambda candidate: candidate is state,
    )


def _shape_request(*, headers=(), query_string=b"", http_version="1.1"):
    return SimpleNamespace(
        scope={
            "headers": list(headers),
            "query_string": query_string,
            "http_version": http_version,
        }
    )


def test_trace_query_disabled_returns_404_before_auth(monkeypatch) -> None:
    monkeypatch.setattr(
        routes_observability,
        "get_observability_settings",
        lambda: _settings(False),
    )

    def fail_auth(request):
        del request
        raise AssertionError(
            "authentication must not run while trace query is disabled"
        )

    monkeypatch.setattr(routes_observability, "_request_identity", fail_auth)
    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}


def test_trace_query_inactive_backend_returns_404_before_auth(monkeypatch) -> None:
    monkeypatch.setattr(
        routes_observability,
        "get_observability_settings",
        lambda: _settings(True),
    )
    monkeypatch.setattr(
        routes_observability,
        "get_observability_backend",
        lambda: NOOP_BACKEND,
    )

    def fail_auth(request):
        del request
        raise AssertionError(
            "authentication must not run while observability backend is inactive"
        )

    monkeypatch.setattr(routes_observability, "_request_identity", fail_auth)
    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}


def test_trace_query_enabled_uses_existing_authentication_response(monkeypatch) -> None:
    monkeypatch.setattr(
        routes_observability,
        "get_observability_settings",
        lambda: _settings(True),
    )
    monkeypatch.setattr(
        routes_observability,
        "get_observability_backend",
        _active_backend,
    )

    def deny_auth(request):
        del request
        raise IdentityResolutionError("authentication required")

    monkeypatch.setattr(routes_observability, "_request_identity", deny_auth)
    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 401
    assert response.json() == {"error": "authentication required"}


def test_trace_query_rejects_query_string_before_index(monkeypatch) -> None:
    _enable_route(monkeypatch)

    def fail_index():
        raise AssertionError("index must not be read for invalid request shape")

    monkeypatch.setattr(routes_observability, "_query_index_state", fail_index)
    response = TestClient(app).get(
        f"/api/observability/traces/{TRACE_ID}", params={"x": "y"}
    )
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}


def test_trace_query_rejects_positive_content_length_without_body_parse(
    monkeypatch,
) -> None:
    _enable_route(monkeypatch)

    def fail_index():
        raise AssertionError("index must not be read for non-empty body framing")

    monkeypatch.setattr(routes_observability, "_query_index_state", fail_index)
    response = TestClient(app).request(
        "GET",
        f"/api/observability/traces/{TRACE_ID}",
        content=b"x",
    )
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}


def test_trace_query_rejects_transfer_encoding_presence(monkeypatch) -> None:
    _enable_route(monkeypatch)

    def fail_index():
        raise AssertionError("index must not be read for transfer encoding")

    monkeypatch.setattr(routes_observability, "_query_index_state", fail_index)
    response = TestClient(app).get(
        f"/api/observability/traces/{TRACE_ID}",
        headers={"Transfer-Encoding": "chunked"},
    )
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}


def test_trace_query_request_shape_enforces_canonical_framing() -> None:
    deadline = time.monotonic() + 5.0
    assert routes_observability._request_shape_is_valid(
        _shape_request(headers=[(b"Content-Length", b"0")]),
        deadline=deadline,
    )
    assert not routes_observability._request_shape_is_valid(
        _shape_request(headers=[(b"content-length", b"0"), (b"content-length", b"0")]),
        deadline=deadline,
    )
    assert not routes_observability._request_shape_is_valid(
        _shape_request(headers=[(b"content-length", b"00")]),
        deadline=deadline,
    )
    assert not routes_observability._request_shape_is_valid(
        _shape_request(http_version="2"),
        deadline=deadline,
    )


def test_trace_query_invalid_trace_id_precedes_index(monkeypatch) -> None:
    _enable_route(monkeypatch)

    def fail_index():
        raise AssertionError("index must not be read for invalid trace id")

    monkeypatch.setattr(routes_observability, "_query_index_state", fail_index)
    response = TestClient(app).get("/api/observability/traces/ABC")
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_trace_id"}


def test_trace_query_missing_local_index_returns_fixed_404(monkeypatch) -> None:
    _enable_route(monkeypatch)
    state = routes_observability._TraceQueryIndexState(
        index=TraceOwnershipIndex(), epoch=3
    )
    _bind_state(monkeypatch, state)
    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def test_trace_query_authorized_personal_trace_reaches_backend_unavailable(
    monkeypatch,
) -> None:
    _enable_route(monkeypatch, principal_id="alice")
    state = _state_with_segment(principal_id="alice")
    _bind_state(monkeypatch, state)
    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 503
    assert response.json() == {"error": "trace_query_unavailable"}


def test_trace_query_personal_trace_rejects_other_principal(monkeypatch) -> None:
    _enable_route(monkeypatch, principal_id="bob")
    state = _state_with_segment(principal_id="alice")
    _bind_state(monkeypatch, state)
    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def test_trace_query_revalidates_live_identity_for_each_owned_span(monkeypatch) -> None:
    monkeypatch.setattr(
        routes_observability,
        "get_observability_settings",
        lambda: _settings(True),
    )
    monkeypatch.setattr(
        routes_observability,
        "get_observability_backend",
        _active_backend,
    )
    calls = {"count": 0}

    def identity(request):
        del request
        calls["count"] += 1
        if calls["count"] >= 4:
            raise IdentityResolutionError("session revoked")
        return _identity("alice")

    monkeypatch.setattr(routes_observability, "_request_identity", identity)
    state = _state_with_segment(principal_id="alice", with_child=True)
    _bind_state(monkeypatch, state)

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert calls["count"] == 4
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def test_trace_query_revalidates_room_membership_on_every_query(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "memory.sqlite3"
    setup_store = MemoryStore(db_path)
    project_policy = ProjectAccessPolicy(
        setup_store, admin_principals=frozenset({"admin"})
    )
    project_policy.set_membership("admin", "demo", "admin", "admin")
    project_policy.set_membership("admin", "demo", "alice", "viewer")
    project_policy.bind_room("admin", "demo", "room-x")
    room_policy = RoomAccessPolicy(setup_store, admin_principals=frozenset({"admin"}))
    room_policy.set_membership("admin", "room-x", "alice", "member")
    setup_store.close()

    monkeypatch.setattr(
        routes_observability, "_memory_store", lambda: MemoryStore(db_path)
    )
    _enable_route(monkeypatch, principal_id="alice")
    state = _state_with_segment(
        principal_id="alice",
        room_id="room-x",
        project_id="demo",
        server_bound_project=True,
    )
    _bind_state(monkeypatch, state)

    client = TestClient(app)
    allowed = client.get(f"/api/observability/traces/{TRACE_ID}")
    assert allowed.status_code == 503

    revoke_store = MemoryStore(db_path)
    try:
        RoomAccessPolicy(
            revoke_store, admin_principals=frozenset({"admin"})
        ).revoke_membership("admin", "room-x", "alice")
    finally:
        revoke_store.close()

    denied = client.get(f"/api/observability/traces/{TRACE_ID}")
    assert denied.status_code == 404
    assert denied.json() == {"error": "trace_not_found"}


def test_trace_query_shared_room_membership_does_not_grant_other_principal(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "memory.sqlite3"
    setup_store = MemoryStore(db_path)
    try:
        project_policy = ProjectAccessPolicy(
            setup_store, admin_principals=frozenset({"admin"})
        )
        project_policy.set_membership("admin", "demo", "admin", "admin")
        project_policy.set_membership("admin", "demo", "alice", "viewer")
        project_policy.set_membership("admin", "demo", "bob", "viewer")
        project_policy.bind_room("admin", "demo", "room-x")
        room_policy = RoomAccessPolicy(
            setup_store, admin_principals=frozenset({"admin"})
        )
        room_policy.set_membership("admin", "room-x", "alice", "member")
        room_policy.set_membership("admin", "room-x", "bob", "member")
    finally:
        setup_store.close()

    monkeypatch.setattr(
        routes_observability, "_memory_store", lambda: MemoryStore(db_path)
    )
    _enable_route(monkeypatch, principal_id="bob")
    state = _state_with_segment(
        principal_id="alice",
        room_id="room-x",
        project_id="demo",
        server_bound_project=True,
    )
    _bind_state(monkeypatch, state)

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def test_trace_query_generation_removal_overrides_unavailable(monkeypatch) -> None:
    _enable_route(monkeypatch, principal_id="alice")
    state = _state_with_segment(principal_id="alice")
    monkeypatch.setattr(routes_observability, "_query_index_state", lambda: state)

    def remove_generation(candidate) -> bool:
        assert candidate is state
        assert state.index.delete_trace(TRACE_ID)
        return True

    monkeypatch.setattr(
        routes_observability,
        "_query_index_state_is_current",
        remove_generation,
    )
    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}

from __future__ import annotations

from fastapi.testclient import TestClient

from uagent.runtime.identity_context import IdentityContext
from uagent.web_impl.app import app
from uagent.web_impl import routes_api


class _Resolver:
    def __init__(self, principal_id: str):
        self.principal_id = principal_id

    def resolve(self, request):
        del request
        return IdentityContext(self.principal_id, True, "oidc")


class _TrackingStore:
    def __init__(self, store):
        self._store = store
        self.close_calls = 0

    def __getattr__(self, name):
        return getattr(self._store, name)

    def close(self):
        self.close_calls += 1
        self._store.close()


def _track_opened_stores(monkeypatch):
    opened = []
    current_open = routes_api.open_memory_store

    def tracking_open(path):
        store = _TrackingStore(current_open(path))
        opened.append(store)
        return store

    monkeypatch.setattr(routes_api, "open_memory_store", tracking_open)
    return opened


def test_denied_personal_memory_request_closes_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        routes_api, "create_identity_resolver", lambda: _Resolver("alice")
    )
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.delenv("UAGENT_ADMIN_PRINCIPALS", raising=False)
    opened = _track_opened_stores(monkeypatch)

    response = TestClient(app).get(
        "/api/me/memories", params={"project_id": "demo"}
    )

    assert response.status_code == 403
    assert opened
    assert all(store.close_calls >= 1 for store in opened)


def test_denied_room_memory_request_closes_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        routes_api, "create_identity_resolver", lambda: _Resolver("alice")
    )
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "alice")
    opened = _track_opened_stores(monkeypatch)

    response = TestClient(app).get(
        "/api/rooms/room-x/memories", params={"project_id": "demo"}
    )

    assert response.status_code == 403
    assert opened
    assert all(store.close_calls >= 1 for store in opened)

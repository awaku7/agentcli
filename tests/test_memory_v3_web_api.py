from __future__ import annotations

from fastapi.testclient import TestClient

from uagent.runtime.identity_context import IdentityContext
from uagent.web_impl.app import app
from uagent.web_impl import routes_api


class _Resolver:
    def __init__(self, principal: list[str]):
        self.principal = principal

    def resolve(self, request):
        del request
        return IdentityContext(self.principal[0], True, "oidc")


def test_v3_web_api_uses_server_identity_and_room_roles(tmp_path, monkeypatch):
    principal = ["admin"]
    resolver = _Resolver(principal)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    client = TestClient(app)

    assert (
        client.put(
            "/api/rooms/room-x/members/alice", json={"role": "admin"}
        ).status_code
        == 200
    )
    assert (
        client.put("/api/rooms/room-x/members/bob", json={"role": "member"}).status_code
        == 200
    )

    principal[0] = "alice"
    personal = client.post(
        "/api/me/memories", json={"project_id": "demo", "note": "alice only"}
    )
    assert personal.status_code == 200
    room = client.post(
        "/api/rooms/room-x/memories",
        json={"project_id": "demo", "note": "room evidence"},
    )
    assert room.status_code == 200

    principal[0] = "bob"
    mine = client.get("/api/me/memories", params={"project_id": "demo"})
    assert mine.status_code == 200
    assert mine.json()["memories"] == []
    shared = client.get("/api/rooms/room-x/memories", params={"project_id": "demo"})
    assert [item["note"] for item in shared.json()["memories"]] == ["room evidence"]
    denied = client.post(
        "/api/rooms/room-x/memories",
        json={"project_id": "demo", "note": "member cannot write"},
    )
    assert denied.status_code == 403
    assert client.get("/api/memories").status_code == 403

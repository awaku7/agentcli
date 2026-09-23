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


def test_v3_web_api_personal_read_grant_lifecycle(tmp_path, monkeypatch):
    principal = ["alice"]
    resolver = _Resolver(principal)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    client = TestClient(app)

    created = client.post(
        "/api/me/memories", json={"project_id": "demo", "note": "private note"}
    )
    assert created.status_code == 200
    memory = created.json()["memory"]
    memory_id = memory["memory_id"]
    revision = memory["revision"]

    granted = client.post(
        f"/api/me/memories/{memory_id}/grants",
        json={
            "project_id": "demo",
            "grantee_principal_id": "bob",
            "expected_revision": revision,
        },
    )
    assert granted.status_code == 200
    grant_id = granted.json()["grant_id"]
    assert (
        client.get(
            f"/api/me/memories/{memory_id}/grants", params={"project_id": "demo"}
        ).json()["grants"][0]["grantee_principal_id"]
        == "bob"
    )

    principal[0] = "bob"
    assert (
        client.get("/api/me/memories", params={"project_id": "demo"}).json()["memories"]
        == []
    )
    shared = client.get("/api/me/shared-memories", params={"project_id": "demo"})
    assert [item["note"] for item in shared.json()["memories"]] == ["private note"]
    assert (
        client.get(
            f"/api/me/shared-memories/{memory_id}", params={"project_id": "demo"}
        ).json()["memory"]["note"]
        == "private note"
    )

    principal[0] = "alice"
    revoked = client.request(
        "DELETE",
        f"/api/me/memories/{memory_id}/grants/{grant_id}",
        json={"project_id": "demo"},
    )
    assert revoked.status_code == 200
    principal[0] = "bob"
    assert (
        client.get("/api/me/shared-memories", params={"project_id": "demo"}).json()[
            "memories"
        ]
        == []
    )


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

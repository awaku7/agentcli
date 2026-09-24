from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from uagent.runtime.identity_context import IdentityContext
from uagent.web_impl.app import app
from uagent.web_impl import routes_api


class _Resolver:
    def __init__(self, principal: list[str], authn_kind: str = "oidc"):
        self.principal = principal
        self.authn_kind = authn_kind

    def resolve(self, request):
        del request
        return IdentityContext(self.principal[0], True, self.authn_kind)


def test_v3_web_api_personal_read_grant_lifecycle(tmp_path, monkeypatch):
    principal = ["admin"]
    resolver = _Resolver(principal)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    client = TestClient(app)

    assert (
        client.put(
            "/api/projects/demo/members/alice", json={"role": "editor"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/projects/demo/members/bob", json={"role": "viewer"}
        ).status_code
        == 200
    )
    principal[0] = "alice"
    assert (
        client.post("/api/project-context", json={"project_id": "demo"}).status_code
        == 200
    )
    assert (
        client.post("/api/project-context", json={"project_id": "other"}).status_code
        == 403
    )
    assert (
        client.get("/api/me/memories", params={"project_id": "other"}).status_code
        == 403
    )

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
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    client = TestClient(app)

    assert (
        client.put(
            "/api/projects/demo/members/alice", json={"role": "editor"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/projects/demo/members/bob", json={"role": "viewer"}
        ).status_code
        == 200
    )
    assert client.put("/api/projects/demo/rooms/room-x").status_code == 200
    assert (
        client.put(
            "/api/rooms/room-x/members/alice",
            json={"project_id": "demo", "role": "admin"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/rooms/room-x/members/bob",
            json={"project_id": "demo", "role": "member"},
        ).status_code
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
    personal_write_denied = client.post(
        "/api/me/memories", json={"project_id": "demo", "note": "viewer cannot write"}
    )
    assert personal_write_denied.status_code == 403
    shared = client.get("/api/rooms/room-x/memories", params={"project_id": "demo"})
    assert [item["note"] for item in shared.json()["memories"]] == ["room evidence"]
    denied = client.post(
        "/api/rooms/room-x/memories",
        json={"project_id": "demo", "note": "member cannot write"},
    )
    assert denied.status_code == 403
    assert client.get("/api/memories").status_code == 403


def test_v3_project_memory_api_enforces_project_roles(tmp_path, monkeypatch):
    principal = ["admin"]
    resolver = _Resolver(principal)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    client = TestClient(app)

    assert (
        client.put(
            "/api/projects/demo/members/alice", json={"role": "editor"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/projects/demo/members/bob", json={"role": "viewer"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/projects/other/memories", json={"note": "wrong project"}
        ).status_code
        == 403
    )

    principal[0] = "alice"
    created = client.post(
        "/api/projects/demo/memories", json={"note": "shared project guidance"}
    )
    assert created.status_code == 200
    memory = created.json()["memory"]
    assert memory["audience_type"] == "project"
    assert memory["audience_id"] == "demo"

    principal[0] = "bob"
    listed = client.get("/api/projects/demo/memories")
    assert [item["note"] for item in listed.json()["memories"]] == [
        "shared project guidance"
    ]
    denied = client.post(
        "/api/projects/demo/memories", json={"note": "viewer cannot write"}
    )
    assert denied.status_code == 403

    principal[0] = "alice"
    deleted = client.request(
        "DELETE",
        f"/api/projects/demo/memories/{memory['memory_id']}",
        json={"expected_revision": memory["revision"]},
    )
    assert deleted.status_code == 200
    principal[0] = "bob"
    assert client.get("/api/projects/demo/memories").json()["memories"] == []


def test_private_room_endpoint_issues_owner_bound_project_session(
    tmp_path, monkeypatch
):
    principal = ["admin"]
    resolver = _Resolver(principal)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    monkeypatch.setattr(routes_api.core, "session_store", None, raising=False)
    client = TestClient(app)

    assert (
        client.put(
            "/api/projects/demo/members/alice", json={"role": "editor"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/projects/demo/members/bob", json={"role": "viewer"}
        ).status_code
        == 200
    )
    principal[0] = "alice"
    response = client.post("/api/me/private-room")
    assert response.status_code == 200
    payload = response.json()
    assert payload["private"] is True
    assert payload["project_id"] == "demo"
    room_id = payload["room_id"]
    blocked_history_command = client.post(
        "/api/command", json={"room_id": room_id, "command": ":load 0"}
    )
    assert blocked_history_command.status_code == 403

    from uagent.runtime.identity_context import IdentityResolutionError
    from uagent.runtime.memory_access import MemoryAccessError
    from uagent.runtime.memory_store import MemoryStore
    from uagent.runtime.room_access import RoomAccessPolicy
    from uagent.web_impl.connection_identity import require_room_access

    store = MemoryStore(tmp_path / "memory.sqlite3")
    policy = RoomAccessPolicy(store, admin_principals=frozenset({"admin"}))
    assert policy.private_room_owner(room_id) == "alice"
    assert policy.private_room_session_id(room_id)
    assert policy.is_private_room_for("alice", room_id)
    with pytest.raises(MemoryAccessError):
        policy.set_membership("admin", room_id, "bob", "member")
    store.close()

    assert require_room_access(IdentityContext("alice", True, "oidc"), room_id) == (
        "demo",
        True,
    )
    with pytest.raises(IdentityResolutionError):
        require_room_access(IdentityContext("bob", True, "oidc"), room_id)

    personal = client.post(
        "/api/me/memories",
        json={"project_id": "demo", "room_id": room_id, "note": "alice private fact"},
    )
    assert personal.status_code == 200, personal.json()
    alice_memory = personal.json()["memory"]["memory_id"]
    own = client.get(
        "/api/me/memories",
        params={"project_id": "demo", "room_id": room_id},
    )
    assert [item["memory_id"] for item in own.json()["memories"]] == [alice_memory]

    principal[0] = "bob"
    denied = client.get(
        "/api/me/memories",
        params={"project_id": "demo", "room_id": room_id},
    )
    assert denied.status_code == 403


def test_authenticated_logs_are_filtered_to_the_current_principal(
    tmp_path, monkeypatch
):
    from uagent.runtime.session_store import SessionStore

    principal = ["alice"]
    resolver = _Resolver(principal)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    store = SessionStore(tmp_path / "sessions.sqlite3")
    alice = store.create_session(project="demo", entry_point="web")
    bob = store.create_session(project="demo", entry_point="web")
    store.bind_identity_context(
        alice.session_id, principal_id="alice", room_id="private-a"
    )
    store.bind_identity_context(bob.session_id, principal_id="bob", room_id="private-b")
    store.append_message(alice.session_id, "user", "Alice secret session")
    store.append_message(bob.session_id, "user", "Bob private session")
    monkeypatch.setattr(routes_api.core, "session_store", store, raising=False)
    monkeypatch.setattr(routes_api.core, "session_id", "current", raising=False)
    client = TestClient(app)

    alice_logs = client.get("/api/logs").json()["logs"]
    assert [row["path"] for row in alice_logs] == [alice.session_id]
    assert (
        client.get(
            "/api/logs/preview-by-path", params={"path": bob.session_id}
        ).status_code
        == 404
    )

    principal[0] = "bob"
    bob_logs = client.get("/api/logs").json()["logs"]
    assert [row["path"] for row in bob_logs] == [bob.session_id]
    assert (
        client.get(
            "/api/logs/preview-by-path", params={"path": alice.session_id}
        ).status_code
        == 404
    )
    store.close()


def test_private_room_local_mode_binds_only_the_current_project(tmp_path, monkeypatch):
    resolver = _Resolver(["local"], authn_kind="local")
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setattr(routes_api.core, "session_store", None, raising=False)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    client = TestClient(app)

    response = client.post("/api/me/private-room")
    assert response.status_code == 200
    room_id = response.json()["room_id"]

    from uagent.runtime.memory_store import MemoryStore
    from uagent.runtime.project_access import ProjectAccessPolicy
    from uagent.runtime.room_access import RoomAccessPolicy

    store = MemoryStore(tmp_path / "memory.sqlite3")
    local_projects = ProjectAccessPolicy(store)
    assert local_projects.can_access("local", "demo", "editor")
    assert RoomAccessPolicy(store).is_private_room_for("local", room_id)
    store.close()

    created = client.post(
        "/api/me/memories",
        json={"project_id": "demo", "room_id": room_id, "note": "local private memory"},
    )
    assert created.status_code == 200, created.json()


def test_private_room_non_oidc_project_selection_is_membership_checked(
    tmp_path, monkeypatch
):
    resolver = _Resolver(["alice"], authn_kind="trusted_proxy")
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setattr(routes_api.core, "session_store", None, raising=False)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.delenv("UAGENT_MEMORY_PROJECT", raising=False)
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "trusted_proxy")
    monkeypatch.setenv("UAGENT_OIDC_COOKIE_SECURE", "0")

    from uagent.runtime.memory_store import MemoryStore
    from uagent.runtime.project_access import ProjectAccessPolicy

    store = MemoryStore(tmp_path / "memory.sqlite3")
    project_policy = ProjectAccessPolicy(store, admin_principals=frozenset({"root"}))
    project_policy.set_membership("root", "demo", "alice", "viewer")
    project_policy.set_membership("root", "second", "alice", "viewer")
    store.close()
    client = TestClient(app)

    projects = client.get("/api/me/projects")
    assert projects.status_code == 200
    assert projects.json()["projects"] == ["demo", "second"]
    missing_selection = client.post("/api/me/private-room")
    assert missing_selection.status_code == 403

    created = client.post("/api/me/private-room", json={"project_id": "demo"})
    assert created.status_code == 200
    assert created.json()["project_id"] == "demo"
    assert created.json()["private"] is True

    denied = client.post("/api/me/private-room", json={"project_id": "other"})
    assert denied.status_code == 403

    selected = client.post("/api/project-context", json={"project_id": "demo"})
    assert selected.status_code == 200
    assert "httponly" in selected.headers["set-cookie"].lower()
    selected_projects = client.get("/api/me/projects").json()
    assert selected_projects["projects"] == ["demo", "second"]
    assert selected_projects["bound_project"] == "demo"
    assert (
        client.get("/api/me/memories", params={"project_id": "demo"}).status_code == 200
    )
    assert (
        client.get("/api/me/memories", params={"project_id": "other"}).status_code
        == 403
    )

    resolver.principal[0] = "mallory"
    assert (
        client.get("/api/me/memories", params={"project_id": "demo"}).status_code == 403
    )
    resolver.principal[0] = "alice"
    assert client.get("/api/me/projects").json()["bound_project"] == "demo"
    switched = client.post("/api/project-context", json={"project_id": "second"})
    assert switched.status_code == 200
    assert client.get("/api/me/projects").json()["bound_project"] == "second"
    context_bound_room = client.post("/api/me/private-room")
    assert context_bound_room.status_code == 200
    assert context_bound_room.json()["project_id"] == "second"
    monkeypatch.setenv("UAGENT_PROJECT_CONTEXT_TTL", "3600")
    assert (
        client.get("/api/me/memories", params={"project_id": "second"}).status_code
        == 403
    )


def test_denied_private_room_request_does_not_allocate_a_web_room(
    tmp_path, monkeypatch
):
    principal = ["alice"]
    resolver = _Resolver(principal)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setattr(routes_api.core, "session_store", None, raising=False)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "root")

    from uagent.runtime.memory_store import MemoryStore
    from uagent.runtime.project_access import ProjectAccessPolicy

    store = MemoryStore(tmp_path / "memory.sqlite3")
    ProjectAccessPolicy(store, admin_principals=frozenset({"root"})).set_membership(
        "root", "demo", "bob", "viewer"
    )
    store.close()

    rooms_before = set(routes_api.web_manager.rooms)
    response = TestClient(app).post("/api/me/private-room")

    assert response.status_code == 403
    assert set(routes_api.web_manager.rooms) == rooms_before

from __future__ import annotations

import asyncio
import hashlib
import json
import threading

from fastapi.testclient import TestClient

from uagent.runtime.enterprise_identity import register_directory_group_policy_adapter
from uagent.runtime.identity_context import IdentityContext
from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.project_access import ProjectAccessPolicy
from uagent.web_impl import routes_api
from uagent.web_impl.app import app


class _Resolver:
    def __init__(
        self,
        principal: str,
        *,
        authenticated: bool = True,
        authn_kind: str = "oidc",
        groups: tuple[str, ...] = (),
    ) -> None:
        self.principal = principal
        self.authenticated = authenticated
        self.authn_kind = authn_kind
        self.groups = groups

    def resolve(self, request):
        del request
        return IdentityContext(
            self.principal,
            self.authenticated,
            self.authn_kind,
            groups=self.groups,
        )


def _directory_policy() -> str:
    return json.dumps(
        {
            "groups": {
                "admins": {
                    "administrator": True,
                    "projects": ["demo"],
                },
                "viewers": {
                    "projects": ["demo"],
                },
            }
        }
    )


def test_process_wide_web_controls_require_auth_and_admin(monkeypatch):
    resolver = _Resolver("alice")
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    monkeypatch.setattr(routes_api.core, "tools_enabled", True, raising=False)

    cleanup_calls: list[bool] = []

    def cleanup(*, execute=True):
        cleanup_calls.append(bool(execute))
        return {"ok": True, "execute": bool(execute)}

    monkeypatch.setattr(
        routes_api.core,
        "artifact_cleanup_report",
        lambda: {"ok": True, "dry_run": True},
        raising=False,
    )
    monkeypatch.setattr(
        routes_api.core,
        "artifact_cleanup",
        cleanup,
        raising=False,
    )
    client = TestClient(app)

    resolver.authenticated = False
    assert client.get("/api/tools-enabled").status_code == 401

    resolver.authenticated = True
    assert client.get("/api/tools-enabled").status_code == 200
    assert client.post("/api/tools-enabled", json={"enabled": False}).status_code == 403
    assert client.get("/api/artifacts/cleanup/report").status_code == 403
    assert (
        client.post(
            "/api/artifacts/cleanup",
            json={"execute": True, "confirm": "DELETE"},
        ).status_code
        == 403
    )
    assert cleanup_calls == []

    resolver.principal = "admin"
    assert client.get("/api/artifacts/cleanup/report").status_code == 200
    assert client.post("/api/tools-enabled", json={"enabled": True}).status_code == 200
    response = client.post(
        "/api/artifacts/cleanup",
        json={"execute": True, "confirm": "DELETE"},
    )
    assert response.status_code == 200
    assert cleanup_calls == [True]


def test_project_membership_revocation_invalidates_matching_sandbox_scope(
    monkeypatch,
):
    calls = []
    release_thread_ids = []
    caller_thread_id = threading.get_ident()
    identity = IdentityContext("admin", True, "local")

    class Store:
        def close(self):
            calls.append("store-closed")

    class Policy:
        def __init__(self, _store):
            pass

        def revoke_membership(self, actor, project, principal):
            calls.append(("revoke", actor, project, principal))

    monkeypatch.setattr(routes_api, "_request_identity", lambda _request: identity)
    monkeypatch.setattr(
        routes_api, "_project_id", lambda project_id, _request: project_id
    )
    monkeypatch.setattr(routes_api, "_memory_store", Store)
    monkeypatch.setattr(routes_api, "ProjectAccessPolicy", Policy)

    def release_scopes(**filters):
        release_thread_ids.append(threading.get_ident())
        calls.append(("release", filters))
        return 1

    monkeypatch.setattr(
        routes_api.web_manager, "release_sandbox_scopes", release_scopes
    )

    result = asyncio.run(
        routes_api.delete_project_member("project-a", "alice", object())
    )

    assert result == {"ok": True}
    assert len(release_thread_ids) == 1
    assert release_thread_ids[0] != caller_thread_id
    assert calls == [
        ("revoke", "admin", "project-a", "alice"),
        "store-closed",
        (
            "release",
            {"principal_id": "alice", "project_id": "project-a"},
        ),
    ]


def test_http_mutations_require_allowed_origin_outside_local(monkeypatch):
    resolver = _Resolver("admin", authn_kind="trusted_proxy")
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "trusted_proxy")
    monkeypatch.setenv(
        "UAGENT_WEB_ALLOWED_ORIGINS",
        "https://uag.corp.example",
    )
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    monkeypatch.setattr(routes_api.core, "tools_enabled", True, raising=False)
    client = TestClient(app)

    missing = client.post("/api/tools-enabled", json={"enabled": False})
    assert missing.status_code == 403
    assert routes_api.core.tools_enabled is True

    cross_site = client.post(
        "/api/tools-enabled",
        content='{"enabled": false}',
        headers={
            "Content-Type": "text/plain",
            "Origin": "https://evil.example",
        },
    )
    assert cross_site.status_code == 403
    assert routes_api.core.tools_enabled is True

    allowed = client.post(
        "/api/tools-enabled",
        json={"enabled": False},
        headers={"Origin": "https://uag.corp.example"},
    )
    assert allowed.status_code == 200
    assert routes_api.core.tools_enabled is False


def test_token_mode_mutation_allows_bearer_without_origin(monkeypatch):
    credential = "service-token"
    namespace = "services"
    subject = "automation"
    digest = hashlib.sha256(credential.encode()).hexdigest()
    principal = (
        "token:" + hashlib.sha256((namespace + "\0" + subject).encode()).hexdigest()
    )
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "token")
    monkeypatch.setenv("UAGENT_TOKEN_NAMESPACE", namespace)
    monkeypatch.setenv(
        "UAGENT_TOKEN_IDENTITIES",
        json.dumps([{"token_sha256": digest, "subject": subject}]),
    )
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", principal)
    monkeypatch.delenv("UAGENT_WEB_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setattr(routes_api.core, "tools_enabled", True, raising=False)
    client = TestClient(app)

    response = client.post(
        "/api/tools-enabled",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {credential}"},
    )

    assert response.status_code == 200
    assert routes_api.core.tools_enabled is False


def test_directory_policy_downgrades_admin_to_viewer(tmp_path, monkeypatch):
    register_directory_group_policy_adapter(None)
    monkeypatch.setenv("UAGENT_DIRECTORY_GROUP_POLICY", _directory_policy())
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "root")
    store = MemoryStore(tmp_path / "memory.sqlite3")
    policy = ProjectAccessPolicy(store)
    try:
        policy.sync_directory_policy(
            IdentityContext("alice", True, "oidc", groups=("admins",))
        )
        assert policy.can_access("alice", "demo", "admin")
        assert policy.membership("alice", "demo").role == "admin"

        policy.sync_directory_policy(
            IdentityContext("alice", True, "oidc", groups=("viewers",))
        )
        assert policy.membership("alice", "demo").role == "viewer"
        assert policy.can_access("alice", "demo", "viewer")
        assert not policy.can_access("alice", "demo", "admin")
    finally:
        store.close()
        register_directory_group_policy_adapter(None)


def test_management_api_refreshes_directory_role_before_admin_check(
    tmp_path, monkeypatch
):
    register_directory_group_policy_adapter(None)
    resolver = _Resolver("alice", groups=("admins",))
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "root")
    monkeypatch.setenv("UAGENT_DIRECTORY_GROUP_POLICY", _directory_policy())
    client = TestClient(app)

    try:
        first = client.get("/api/projects/demo/members")
        assert first.status_code == 200, first.text

        resolver.groups = ("viewers",)
        second = client.get("/api/projects/demo/members")
        assert second.status_code == 403, second.text

        store = MemoryStore(tmp_path / "memory.sqlite3")
        try:
            membership = ProjectAccessPolicy(store).membership("alice", "demo")
            assert membership is not None
            assert membership.role == "viewer"
        finally:
            store.close()
    finally:
        register_directory_group_policy_adapter(None)


def test_project_room_binding_only_releases_scope_after_a_real_change(monkeypatch):
    identity = IdentityContext("admin", True, "local")
    binding_changed = {"value": False}
    release_thread_ids = []
    caller_thread_id = threading.get_ident()

    class Store:
        def close(self):
            pass

    class Policy:
        def __init__(self, _store):
            pass

        def bind_room(self, _actor, _project, _room):
            return binding_changed["value"]

    monkeypatch.setattr(routes_api, "_request_identity", lambda _request: identity)
    monkeypatch.setattr(
        routes_api, "_project_id", lambda project_id, _request: project_id
    )
    monkeypatch.setattr(routes_api, "_memory_store", Store)
    monkeypatch.setattr(routes_api, "ProjectAccessPolicy", Policy)
    monkeypatch.setattr(
        routes_api.web_manager,
        "release_sandbox_scopes",
        lambda **_filters: release_thread_ids.append(threading.get_ident()),
    )

    unchanged = asyncio.run(
        routes_api.bind_project_room("project-a", "room-a", object())
    )
    assert unchanged == {
        "ok": True,
        "project_id": "project-a",
        "room_id": "room-a",
    }
    assert release_thread_ids == []

    binding_changed["value"] = True
    changed = asyncio.run(routes_api.bind_project_room("project-a", "room-a", object()))
    assert changed == {
        "ok": True,
        "project_id": "project-a",
        "room_id": "room-a",
    }
    assert len(release_thread_ids) == 1
    assert release_thread_ids[0] != caller_thread_id


def test_room_membership_revocation_offloads_scope_close(monkeypatch):
    identity = IdentityContext("admin", True, "local")
    release_thread_ids = []
    caller_thread_id = threading.get_ident()

    class Request:
        async def json(self):
            return {"project_id": "project-a"}

    class Store:
        def close(self):
            pass

    class ProjectPolicy:
        def __init__(self, _store):
            pass

        def require_access(self, *_args):
            pass

        def require_room_binding(self, *_args):
            pass

    class RoomPolicy:
        def __init__(self, _store):
            pass

        def revoke_membership(self, *_args):
            pass

    monkeypatch.setattr(routes_api, "_request_identity", lambda _request: identity)
    monkeypatch.setattr(routes_api, "_project_id", lambda value, _request: value)
    monkeypatch.setattr(routes_api, "_memory_store", Store)
    monkeypatch.setattr(routes_api, "ProjectAccessPolicy", ProjectPolicy)
    monkeypatch.setattr(routes_api, "RoomAccessPolicy", RoomPolicy)
    monkeypatch.setattr(
        routes_api.web_manager,
        "release_sandbox_scopes",
        lambda **_filters: release_thread_ids.append(threading.get_ident()),
    )

    result = asyncio.run(routes_api.delete_room_member("room-a", "alice", Request()))

    assert result == {"ok": True}
    assert len(release_thread_ids) == 1
    assert release_thread_ids[0] != caller_thread_id

from __future__ import annotations

import json

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
    assert client.get("/api/tool-genres").status_code == 200
    assert client.post("/api/tools-enabled", json={"enabled": False}).status_code == 403
    assert (
        client.post(
            "/api/tool-genres",
            json={"genre": "__invalid__", "enabled": True},
        ).status_code
        == 403
    )
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
    assert (
        client.post(
            "/api/tool-genres",
            json={"genre": "__invalid__", "enabled": True},
        ).status_code
        == 400
    )
    response = client.post(
        "/api/artifacts/cleanup",
        json={"execute": True, "confirm": "DELETE"},
    )
    assert response.status_code == 200
    assert cleanup_calls == [True]


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

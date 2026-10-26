from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import pytest

from uagent.runtime.identity_context import IdentityContext
from uagent.runtime import instance_identity
from uagent.web_impl import routes_api
from uagent.web_impl.app import app
from uagent.web_impl import routes_integration  # noqa: F401  registers API route


class _Resolver:
    def __init__(self, principal: str, authenticated: bool = True) -> None:
        self.principal = principal
        self.authenticated = authenticated

    def resolve(self, request):
        del request
        return IdentityContext(
            self.principal,
            self.authenticated,
            "oidc",
        )


def test_instance_id_is_persisted_and_stable(tmp_path, monkeypatch):
    monkeypatch.delenv("UAGENT_INSTANCE_ID", raising=False)
    monkeypatch.setattr(instance_identity, "get_state_dir", lambda: tmp_path)

    first = instance_identity.get_instance_id()
    second = instance_identity.get_instance_id()

    assert first == second
    assert (tmp_path / "instance_id").read_text(encoding="ascii").strip() == first


def test_concurrent_first_use_persists_one_instance_id(tmp_path, monkeypatch):
    monkeypatch.delenv("UAGENT_INSTANCE_ID", raising=False)
    monkeypatch.setattr(instance_identity, "get_state_dir", lambda: tmp_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        instance_ids = list(
            executor.map(lambda _item: instance_identity.get_instance_id(), range(32))
        )

    assert len(set(instance_ids)) == 1
    assert (tmp_path / "instance_id").read_text(
        encoding="ascii"
    ).strip() == instance_ids[0]


def test_instance_id_accepts_configured_uuid_and_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("UAGENT_INSTANCE_ID", "{12345678-1234-5678-1234-567812345678}")
    assert instance_identity.get_instance_id() == "12345678-1234-5678-1234-567812345678"

    monkeypatch.setenv("UAGENT_INSTANCE_ID", "not-a-uuid")
    with pytest.raises(ValueError, match="valid UUID"):
        instance_identity.get_instance_id()


def test_integration_manifest_is_admin_only_and_contains_no_credentials(monkeypatch):
    resolver = _Resolver("member")
    monkeypatch.delenv("UAGENT_MANAGEMENT_API_TOKEN", raising=False)
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    monkeypatch.setenv("UAGENT_INSTANCE_ID", "12345678-1234-5678-1234-567812345678")
    monkeypatch.setenv("UAGENT_INSTANCE_NAME", "staging-agent")
    client = TestClient(app)

    resolver.authenticated = False
    assert client.get("/api/admin/integration/v1/manifest").status_code == 401

    resolver.authenticated = True
    assert client.get("/api/admin/integration/v1/manifest").status_code == 403

    resolver.principal = "admin"
    response = client.get("/api/admin/integration/v1/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "1"
    assert body["instance"] == {
        "id": "12345678-1234-5678-1234-567812345678",
        "name": "staging-agent",
    }
    assert body["software"]["name"] == "uag"
    assert body["supported_entrypoints"] == ["cli", "web", "gui", "a2a"]
    assert body["capabilities"] == ["instance.identity.read"]
    assert "token" not in response.text.lower()

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/admin/integration/v1/manifest" not in openapi.json()["paths"]


def test_integration_manifest_accepts_scoped_management_bearer(monkeypatch):
    token = "management-service-test-token-with-more-than-32-bytes"
    monkeypatch.setenv("UAGENT_MANAGEMENT_API_TOKEN", token)
    monkeypatch.setenv("UAGENT_INSTANCE_ID", "12345678-1234-5678-1234-567812345678")
    monkeypatch.setenv("UAGENT_INSTANCE_NAME", "managed-agent")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "admin")
    resolver = _Resolver("member")
    monkeypatch.setattr(routes_api, "create_identity_resolver", lambda: resolver)
    client = TestClient(app)

    response = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["instance"]["name"] == "managed-agent"

    invalid = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": "Bearer incorrect-management-token"},
    )
    assert invalid.status_code == 401

    # The service credential is intentionally scoped to this read-only route.
    other_admin_route = client.get(
        "/api/artifacts/cleanup/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert other_admin_route.status_code == 403

"""C1 integration: signed operator proof, scoped bearer, atomic replay guard."""

from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
import os
import time
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
import pytest

from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.project_access import ProjectAccessPolicy
from uagent.web_impl import routes_integration  # noqa: F401
from uagent.web_impl.app import app

INSTANCE = "12345678-1234-5678-1234-567812345678"
PROJECT = "project-a"
WRITE_TOKEN = "write-only-project-token-0123456789-ABCD"
MANIFEST_TOKEN = "manifest-only-project-token-0123456789"
BASE = f"/api/admin/integration/v1/projects/{PROJECT}/memberships"


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def signed_headers(private, payload, body, *, token=WRITE_TOKEN, **overrides):
    now = int(time.time())
    assertion = {
        "issuer_id": "admin-service-one",
        "actor_user_id": 7,
        "session_version": 3,
        "audience": INSTANCE,
        "project_id": PROJECT,
        "method": "POST",
        "path": BASE,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "issued_at": now,
        "expires_at": now + 45,
        "nonce": uuid4().hex,
    }
    assertion.update(overrides)
    data = json.dumps(assertion, sort_keys=True, separators=(",", ":")).encode()
    signature = private.sign(data)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-UAG-Actor-Assertion": b64(data) + "." + b64(signature),
    }


def request(client, private, payload=None, *, headers=None, route=BASE, **claims):
    if payload is None:
        payload = {
            "action": "grant",
            "target_principal_id": "bob",
            "expected_revision": 1,
            "role": "editor",
        }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    headers = headers or signed_headers(private, payload, raw, **claims)
    return client.post(route, content=raw, headers=headers)


@pytest.fixture
def api(tmp_path, monkeypatch):
    private = Ed25519PrivateKey.generate()
    public_key = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    db_path = tmp_path / "memory.sqlite3"
    with closing(MemoryStore(db_path)) as store:
        policy = ProjectAccessPolicy(store, admin_principals=frozenset({"bootstrap"}))
        policy.set_membership("bootstrap", PROJECT, "alice", "admin")
        policy.set_membership("bootstrap", PROJECT, "second", "admin")
        policy.set_membership("bootstrap", PROJECT, "bob", "viewer")
    monkeypatch.setenv("UAGENT_INSTANCE_ID", INSTANCE)
    monkeypatch.setenv("UAGENT_MANAGEMENT_API_TOKEN", MANIFEST_TOKEN)
    for key in (
        "UAGENT_MANAGEMENT_READ_TOKEN",
        "UAGENT_MANAGEMENT_READ_PRINCIPAL",
        "UAGENT_MANAGEMENT_READ_PROJECT_ID",
        "UAGENT_MANAGEMENT_READ_SCOPES_FILE",
    ):
        monkeypatch.delenv(key, raising=False)
    from uagent.web_impl import routes_integration_write

    monkeypatch.setattr(
        routes_integration_write._long_memory_mod, "is_sqlite_backend", lambda: True
    )
    monkeypatch.setattr(
        routes_integration_write._long_memory_mod, "_sqlite_path", lambda: str(db_path)
    )
    scope_path = tmp_path / "write-scopes.json"

    def configure(token=WRITE_TOKEN, principal="alice", issuer="admin-service-one"):
        scope_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "scopes": [
                        {
                            "instance_id": INSTANCE,
                            "project_id": PROJECT,
                            "principal_id": principal,
                            "token": token,
                            "issuer_id": issuer,
                            "public_key": b64(public_key),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        scope_path.chmod(0o600)
        monkeypatch.setenv("UAGENT_MANAGEMENT_WRITE_SCOPES_FILE", str(scope_path))

    configure()
    yield TestClient(app), private, db_path, configure, scope_path


def test_signed_grant_audit_replay_and_revision(api):
    client, private, path, _, _ = api
    payload = {
        "action": "grant",
        "target_principal_id": "bob",
        "expected_revision": 1,
        "role": "editor",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    headers = signed_headers(private, payload, raw)
    response = client.post(BASE, content=raw, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert response.headers["cache-control"] == "no-store"
    assert client.post(BASE, content=raw, headers=headers).status_code == 409
    assert request(client, private).status_code == 409
    with closing(MemoryStore(path)) as store:
        row = store.db.execute(
            "SELECT actor_principal_id, delegation_issuer, "
            "delegation_actor_user_id, delegation_session_version, delegation_nonce "
            "FROM project_membership_mutation_audit"
        ).fetchone()
        assert tuple(row) == (
            "alice",
            "admin-service-one",
            7,
            3,
            json.loads(
                base64.urlsafe_b64decode(
                    headers["X-UAG-Actor-Assertion"].split(".")[0] + "=="
                )
            )["nonce"],
        )
        assert (
            store.db.execute(
                "SELECT COUNT(*) FROM project_membership_mutation_nonces"
            ).fetchone()[0]
            == 1
        )


def test_reject_unsigned_invalid_token_and_wrong_project(api):
    client, private, _path, _configure, _ = api
    payload = {
        "action": "grant",
        "target_principal_id": "bob",
        "expected_revision": 1,
        "role": "editor",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    assert (
        client.post(
            BASE, content=raw, headers={"Authorization": f"Bearer {WRITE_TOKEN}"}
        ).status_code
        == 401
    )
    assert request(client, private, payload, token=MANIFEST_TOKEN).status_code == 401
    assert request(client, private, payload, token="wrong-token").status_code == 401
    assert (
        request(
            client, private, payload, route=BASE.replace(PROJECT, "other")
        ).status_code
        == 403
    )
    assert (
        request(client, private, payload, audience="other-instance").status_code == 401
    )
    assert request(client, private, payload, project_id="other").status_code == 401
    assert request(client, private, payload, issuer_id="unknown").status_code == 401


def test_assertion_body_tamper_expiry_and_signature_are_rejected(api):
    client, private, path, _configure, _ = api
    payload = {
        "action": "grant",
        "target_principal_id": "bob",
        "expected_revision": 1,
        "role": "editor",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    token = signed_headers(private, payload, raw)
    tampered = {**payload, "role": "admin"}
    assert client.post(BASE, json=tampered, headers=token).status_code == 401
    assert (
        request(client, private, payload, expires_at=int(time.time()) - 1).status_code
        == 401
    )
    assert (
        request(client, private, payload, issued_at=int(time.time()) + 100).status_code
        == 401
    )
    bad = dict(token)
    bad["X-UAG-Actor-Assertion"] = "XX" + bad["X-UAG-Actor-Assertion"][2:]
    assert client.post(BASE, content=raw, headers=bad).status_code == 401
    assert request(client, private, payload, actor_user_id=True).status_code == 401
    assert request(client, private, payload, session_version=True).status_code == 401
    with closing(MemoryStore(path)) as store:
        assert (
            store.db.execute(
                "SELECT COUNT(*) FROM project_membership_mutation_audit"
            ).fetchone()[0]
            == 0
        )


def test_fail_closed_configuration_and_credentials_separation(api, monkeypatch):
    client, private, _path, configure, scope_path = api
    assert (
        "project.membership.write"
        in client.get(
            "/api/admin/integration/v1/manifest",
            headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
        ).json()["capabilities"]
    )
    configure(token=MANIFEST_TOKEN)
    assert request(client, private).status_code == 503
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_TOKEN", WRITE_TOKEN)
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_PRINCIPAL", "alice")
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_PROJECT_ID", PROJECT)
    configure()
    assert request(client, private).status_code == 503
    monkeypatch.delenv("UAGENT_MANAGEMENT_READ_TOKEN")
    monkeypatch.delenv("UAGENT_MANAGEMENT_READ_PRINCIPAL")
    monkeypatch.delenv("UAGENT_MANAGEMENT_READ_PROJECT_ID")
    monkeypatch.delenv("UAGENT_MANAGEMENT_WRITE_SCOPES_FILE")
    assert request(client, private).status_code == 404
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert "project.membership.write" not in manifest.json()["capabilities"]
    monkeypatch.setenv("UAGENT_MANAGEMENT_WRITE_SCOPES_FILE", str(scope_path))
    if os.name != "nt":
        scope_path.chmod(0o644)
        assert request(client, private).status_code == 503


def test_admin_revocation_and_directory_provenance(api):
    client, private, path, configure, _ = api
    configure(principal="bob")
    assert request(client, private).status_code == 403
    configure()
    with closing(MemoryStore(path)) as store:
        store.db.execute(
            "UPDATE project_memberships SET granted_by='directory-policy' "
            "WHERE project_id = ? AND principal_id = 'bob'",
            (PROJECT,),
        )
        store.db.commit()
    assert request(client, private).status_code == 403
    with closing(MemoryStore(path)) as store:
        store.db.execute(
            "UPDATE project_memberships SET status='revoked' "
            "WHERE project_id = ? AND principal_id = 'alice'",
            (PROJECT,),
        )
        store.db.commit()
    assert request(client, private).status_code == 403


def test_final_admin_demotion_is_denied_even_with_revision(api):
    client, private, path, _, _ = api
    with closing(MemoryStore(path)) as store:
        store.db.execute(
            "UPDATE project_memberships SET status='revoked' "
            "WHERE project_id = ? AND principal_id = 'second'",
            (PROJECT,),
        )
        store.db.commit()
    payload = {
        "action": "grant",
        "target_principal_id": "alice",
        "expected_revision": 1,
        "role": "viewer",
    }
    assert request(client, private, payload).status_code == 403
    with closing(MemoryStore(path)) as store:
        row = store.db.execute(
            "SELECT role, status FROM project_memberships "
            "WHERE project_id = ? AND principal_id = 'alice'",
            (PROJECT,),
        ).fetchone()
    assert tuple(row) == ("admin", "active")


def test_failed_audit_rolls_back_signed_nonce_and_member(api):
    client, private, path, _, _ = api
    with closing(MemoryStore(path)) as store:
        store.db.execute(
            "CREATE TRIGGER fail_c1_audit BEFORE INSERT "
            "ON project_membership_mutation_audit "
            "BEGIN SELECT RAISE(FAIL, 'audit failed'); END"
        )
        store.db.commit()
    assert request(client, private).status_code == 503
    with closing(MemoryStore(path)) as store:
        member = store.db.execute(
            "SELECT role, revision FROM project_memberships "
            "WHERE project_id = ? AND principal_id='bob'",
            (PROJECT,),
        ).fetchone()
        assert tuple(member) == ("viewer", 1)
        assert (
            store.db.execute(
                "SELECT COUNT(*) FROM project_membership_mutation_nonces"
            ).fetchone()[0]
            == 0
        )


def test_invalid_json_and_nonce_claims(api):
    client, private, path, _, _ = api
    payload = {
        "action": "grant",
        "target_principal_id": "bob",
        "expected_revision": 1,
        "role": "editor",
    }
    assert request(client, private, payload, nonce="short").status_code == 401
    wrong = {
        "action": "grant",
        "target_principal_id": "bob",
        "expected_revision": True,
        "role": "editor",
    }
    assert request(client, private, wrong).status_code == 400
    no_role = {"action": "grant", "target_principal_id": "bob", "expected_revision": 1}
    assert request(client, private, no_role).status_code == 400
    duplicates = b'{"action":"grant","action":"grant","target_principal_id":"bob","expected_revision":1,"role":"editor"}'
    sig = signed_headers(private, payload, duplicates)
    assert client.post(BASE, content=duplicates, headers=sig).status_code == 400


def test_missing_or_symlink_scope_config_denied(api, tmp_path):
    client, private, _path, _configure, scope_path = api
    if os.name == "nt":
        pytest.skip("Unix symlink path protection")
    replacement = tmp_path / "other-scopes.json"
    replacement.write_bytes(scope_path.read_bytes())
    replacement.chmod(0o600)
    scope_path.unlink()
    scope_path.symlink_to(replacement)
    assert request(client, private).status_code == 503


def test_large_body_rejected_at_stream_boundary(api):
    client, private, path, _configure, _ = api
    assert (
        client.post(
            BASE,
            content=b"x" * 100000,
            headers={
                "Authorization": f"Bearer {WRITE_TOKEN}",
                "Content-Type": "application/json",
            },
        ).status_code
        == 413
    )
    with closing(MemoryStore(path)) as store:
        assert (
            store.db.execute(
                "SELECT COUNT(*) FROM project_membership_mutation_audit"
            ).fetchone()[0]
            == 0
        )


def test_browser_mode_allows_only_no_origin_signed_service_posts(api, monkeypatch):
    """Origin guard must not block machine clients in default browser mode."""
    client, private, path, _configure, _file = api
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "browser")
    response = request(client, private)
    assert response.status_code == 200, response.text

    # A bad browser Origin still goes through the normal Origin guard.
    payload = {
        "action": "grant",
        "target_principal_id": "bob",
        "expected_revision": 2,
        "role": "admin",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    headers = signed_headers(private, payload, raw)
    denied = client.post(
        BASE, content=raw, headers={**headers, "Origin": "https://evil.example"}
    )
    assert denied.status_code == 403
    assert denied.json()["error"] == "request Origin is not allowed"

    # An unsigned no-Origin request is not authenticated by the exemption.
    missing_proof = client.post(
        BASE, content=raw, headers={"Authorization": f"Bearer {WRITE_TOKEN}"}
    )
    assert missing_proof.status_code == 401

    # Do not disable the guard for a sibling route or a browser-facing POST.
    sibling = client.post(BASE + "/other", content=raw, headers=headers)
    assert sibling.status_code == 403
    unrelated = client.post("/api/tools-enabled", json={"enabled": True})
    assert unrelated.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"action": [], "target_principal_id": "bob", "expected_revision": 1},
        {
            "action": {"grant": True},
            "target_principal_id": "bob",
            "expected_revision": 1,
        },
        {
            "action": "grant",
            "target_principal_id": "bob",
            "expected_revision": 1,
            "role": [],
        },
        {
            "action": "grant",
            "target_principal_id": "bob",
            "expected_revision": 1,
            "role": {},
        },
        {
            "action": "grant",
            "target_principal_id": [],
            "expected_revision": 1,
            "role": "editor",
        },
        {
            "action": "grant",
            "target_principal_id": "bob",
            "expected_revision": [],
            "role": "editor",
        },
        {
            "action": "grant",
            "target_principal_id": "bob",
            "expected_revision": True,
            "role": "editor",
        },
    ],
)
def test_signed_malformed_value_types_return_400_not_500(api, payload):
    client, private, path, _configure, _ = api
    response = request(client, private, payload)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_mutation"
    with closing(MemoryStore(path)) as store:
        assert (
            store.db.execute(
                "SELECT COUNT(*) FROM project_membership_mutation_audit"
            ).fetchone()[0]
            == 0
        )

"""Read-only management session contract and authorization regression tests."""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient
import pytest

from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.session_store import SessionStore
from uagent.web_impl import routes_integration
from uagent.web_impl.app import app

TOKEN = "separate-read-service-token-with-at-least-32-characters"
MANIFEST_TOKEN = "manifest-service-token-with-at-least-32-characters"
INSTANCE_ID = "12345678-1234-5678-1234-567812345678"
BASE = "/api/admin/integration/v1/sessions"


@pytest.fixture
def read_client(tmp_path, monkeypatch):
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_TOKEN", TOKEN)
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_PRINCIPAL", "owner-a")
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_PROJECT_ID", "project-a")
    monkeypatch.setenv("UAGENT_MANAGEMENT_API_TOKEN", MANIFEST_TOKEN)
    monkeypatch.setenv("UAGENT_INSTANCE_ID", INSTANCE_ID)
    monkeypatch.setenv("UAGENT_SESSION_STORE", "1")
    path = tmp_path / "sessions.sqlite3"
    with SessionStore(path) as store:
        for project, principal, text in (
            ("project-a", "owner-a", "private-a"),
            ("project-a", "owner-b", "private-b"),
            ("project-b", "owner-a", "private-c"),
        ):
            session = store.create_session(project=project, entry_point="web")
            store.bind_identity_context(
                session.session_id, principal_id=principal, room_id="room"
            )
            store.append_message(session.session_id, "user", text)
    monkeypatch.setenv("UAGENT_SESSION_STORE_PATH", str(path))
    monkeypatch.setattr(
        routes_integration,
        "_authorized_project",
        lambda principal, project: principal == "owner-a" and project == "project-a",
    )
    return TestClient(app), path


def _get(client, *, token=TOKEN, project="project-a", **params):
    return client.get(
        BASE,
        params={"project_id": project, **params},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_sessions_only_selected_owner_project_and_metadata(read_client):
    client, _ = read_client
    response = _get(client)
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "1"
    assert payload["instance_id"] == INSTANCE_ID
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert set(item) == {"id", "project_id", "state", "created_at", "updated_at"}
    assert item["project_id"] == "project-a"
    assert item["created_at"].endswith("Z")
    assert "private-a" not in response.text
    assert "private-b" not in response.text
    assert "private-c" not in response.text
    assert "project_path" not in response.text
    assert payload["next_cursor"] is None


def test_manifest_credential_does_not_grant_history(read_client):
    client, _ = read_client
    assert _get(client, token=MANIFEST_TOKEN).status_code == 401
    assert client.get(BASE, params={"project_id": "project-a"}).status_code == 401


def test_wrong_project_never_reaches_history(read_client):
    client, _ = read_client
    assert _get(client, project="project-b").status_code == 403


def test_unauthorized_project_is_forbidden(read_client, monkeypatch):
    client, _ = read_client
    monkeypatch.setattr(routes_integration, "_authorized_project", lambda *_: False)
    assert _get(client).status_code == 403


def test_project_policy_error_fails_closed(read_client, monkeypatch):
    client, _ = read_client

    def denied(*_args):
        raise RuntimeError("memory store inaccessible")

    monkeypatch.setattr(routes_integration, "_authorized_project", denied)
    assert _get(client).status_code == 503


def test_absent_configuration_has_no_capability(read_client, monkeypatch):
    client, _ = read_client
    for key in (
        "UAGENT_MANAGEMENT_READ_TOKEN",
        "UAGENT_MANAGEMENT_READ_PRINCIPAL",
        "UAGENT_MANAGEMENT_READ_PROJECT_ID",
    ):
        monkeypatch.delenv(key)
    response = _get(client)
    assert response.status_code == 404
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert manifest.status_code == 200
    assert "session.metadata.read" not in manifest.json()["capabilities"]


def test_incomplete_configuration_fails_closed(read_client, monkeypatch):
    client, _ = read_client
    monkeypatch.delenv("UAGENT_MANAGEMENT_READ_PRINCIPAL")
    assert _get(client).status_code == 503


def test_manifest_advertises_opted_in_read_capability(read_client):
    client, _ = read_client
    response = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert response.status_code == 200
    assert "session.metadata.read" in response.json()["capabilities"]


def test_invalid_cursor_and_pagination(read_client):
    client, path = read_client
    with SessionStore(path) as store:
        for _ in range(3):
            session = store.create_session(project="project-a", entry_point="web")
            store.bind_identity_context(
                session.session_id, principal_id="owner-a", room_id="room"
            )
    first = _get(client, limit=2)
    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    cursor = first.json()["next_cursor"]
    assert cursor is not None
    second = _get(client, limit=2, cursor=cursor)
    assert second.status_code == 200
    assert len(second.json()["items"]) == 2
    assert second.json()["next_cursor"] is None
    ids = [item["id"] for item in first.json()["items"] + second.json()["items"]]
    assert len(set(ids)) == 4
    assert _get(client, cursor="not a base64 cursor").status_code == 400


def test_store_unavailable_does_not_leak_data(read_client, monkeypatch):
    client, _ = read_client
    monkeypatch.setattr(routes_integration, "_open_session_store", lambda: None)
    assert _get(client).status_code == 503


@pytest.fixture
def membership_db(tmp_path, monkeypatch):
    """Create explicit and directory-owned project memberships once."""
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    try:
        store.db.execute(
            "INSERT INTO projects(project_id, status, created_at, updated_at) "
            "VALUES ('project-a', 'active', 1, 1)"
        )
        for principal, grant, status in (
            ("owner-a", "human-admin", "active"),
            ("directory-user", "directory-policy", "active"),
            ("revoked-user", "human-admin", "revoked"),
        ):
            store.db.execute(
                "INSERT INTO project_memberships("
                "project_id, principal_id, role, status, granted_by, "
                "created_at, updated_at) VALUES (?, ?, 'viewer', ?, ?, 1, 1)",
                ("project-a", principal, status, grant),
            )
        store.db.commit()
    finally:
        store.close()
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(path))
    return path


def test_management_auth_reads_existing_grants_without_migrations(
    membership_db, monkeypatch
):
    from uagent.runtime import memory_store

    def reject_open(*args, **kwargs):
        raise AssertionError("MemoryStore initialization on metadata GET")

    monkeypatch.setattr(memory_store.MemoryStore, "__init__", reject_open)
    original_connect = sqlite3.connect
    observed = []

    def read_only_connect(database, *args, **kwargs):
        observed.append((str(database), kwargs))
        assert str(database).endswith("?mode=ro")
        assert kwargs.get("uri") is True
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(routes_integration.sqlite3, "connect", read_only_connect)
    assert routes_integration._authorized_project("owner-a", "project-a") is True
    assert observed


def test_management_auth_refuses_cached_directory_grant(membership_db):
    # A removed directory group may leave an active cached row until sync.
    assert (
        routes_integration._authorized_project("directory-user", "project-a") is False
    )


def test_management_auth_refuses_revoked_or_missing_grant(membership_db):
    assert routes_integration._authorized_project("revoked-user", "project-a") is False
    assert routes_integration._authorized_project("not-member", "project-a") is False
    assert routes_integration._authorized_project("owner-a", "project-b") is False


def test_management_auth_refuses_global_admin_without_explicit_grant(
    membership_db, monkeypatch
):
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "global-admin")
    assert routes_integration._authorized_project("global-admin", "project-a") is False


def test_management_auth_fail_closed_on_missing_db(membership_db, monkeypatch):
    missing = membership_db.with_name("missing.sqlite3")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(missing))
    assert routes_integration._authorized_project("owner-a", "project-a") is False
    assert not missing.exists()


def test_management_auth_refuses_revoked_project(membership_db):
    conn = sqlite3.connect(membership_db)
    try:
        conn.execute(
            "UPDATE projects SET status='revoked' WHERE project_id='project-a'"
        )
        conn.commit()
    finally:
        conn.close()
    assert routes_integration._authorized_project("owner-a", "project-a") is False


@pytest.fixture
def members_client(read_client, membership_db):
    client, _ = read_client
    with sqlite3.connect(membership_db) as conn:
        conn.execute(
            "UPDATE project_memberships SET role='admin' "
            "WHERE project_id='project-a' AND principal_id='owner-a'"
        )
        conn.execute(
            "INSERT INTO project_memberships "
            "(project_id, principal_id, role, status, revision, granted_by, "
            "created_at, updated_at) VALUES "
            "('project-a', 'editor-a', 'editor', 'active', 2, 'owner-a', 1, 1)"
        )
        conn.commit()
    return client, membership_db


def _get_members(client, project="project-a", token=TOKEN, **params):
    return client.get(
        f"/api/admin/integration/v1/projects/{project}/members",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_members_only_return_metadata(members_client):
    client, _ = members_client
    response = _get_members(client)
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "api_version",
        "instance_id",
        "project_id",
        "members",
        "next_cursor",
    }
    assert payload["instance_id"] == INSTANCE_ID
    assert payload["project_id"] == "project-a"
    assert {member["principal_id"] for member in payload["members"]} == {
        "owner-a",
        "editor-a",
        "directory-user",
    }
    assert all(
        set(member) == {"principal_id", "role", "revision"}
        for member in payload["members"]
    )
    assert "granted_by" not in response.text
    assert "private-a" not in response.text


def test_members_paginated_and_bounded(members_client):
    client, _ = members_client
    first = _get_members(client, limit=2)
    assert first.status_code == 200
    assert len(first.json()["members"]) == 2
    cursor = first.json()["next_cursor"]
    assert cursor
    second = _get_members(client, cursor=cursor, limit=2)
    assert second.status_code == 200
    assert len(second.json()["members"]) == 1
    assert second.json()["next_cursor"] is None
    assert _get_members(client, limit=101).status_code == 400
    assert _get_members(client, cursor="x" * 257).status_code == 400


def test_members_credential_scope_and_project_binding(members_client):
    client, _ = members_client
    assert _get_members(client, token=MANIFEST_TOKEN).status_code == 401
    missing_token = client.get("/api/admin/integration/v1/projects/project-a/members")
    assert missing_token.status_code == 401
    assert _get_members(client, project="project-b").status_code == 403


def test_members_require_explicit_nondirectory_admin(members_client):
    client, path = members_client
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE project_memberships SET role='viewer' "
            "WHERE project_id='project-a' AND principal_id='owner-a'"
        )
        conn.commit()
    assert _get_members(client).status_code == 403
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE project_memberships SET role='admin', granted_by='directory-policy' "
            "WHERE project_id='project-a' AND principal_id='owner-a'"
        )
        conn.commit()
    assert _get_members(client).status_code == 403


def test_members_revoke_and_failure_closed(members_client, monkeypatch):
    client, path = members_client
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE project_memberships SET status='revoked' "
            "WHERE project_id='project-a' AND principal_id='owner-a'"
        )
        conn.commit()
    assert _get_members(client).status_code == 403
    missing = path.with_name("missing.sqlite3")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(missing))
    assert _get_members(client).status_code == 503
    assert not missing.exists()


def test_members_capability_requires_config(members_client, monkeypatch):
    client, _ = members_client
    url = "/api/admin/integration/v1/manifest"
    headers = {"Authorization": f"Bearer {MANIFEST_TOKEN}"}
    response = client.get(url, headers=headers)
    assert "project.membership.read" in response.json()["capabilities"]
    monkeypatch.delenv("UAGENT_MANAGEMENT_READ_TOKEN")
    response = client.get(url, headers=headers)
    assert "project.membership.read" not in response.json()["capabilities"]
    assert _get_members(client).status_code == 503

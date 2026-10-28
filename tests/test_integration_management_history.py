"""Read-only management session contract and authorization regression tests."""

from __future__ import annotations

import sqlite3
import json
import os

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
    assert _get_members(client, cursor="x" * 257).status_code == 200


def test_members_cursor_can_resume_after_long_principal_id(members_client):
    client, path = members_client
    principal_id = "b" * 257
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO project_memberships "
            "(project_id, principal_id, role, status, granted_by, "
            "created_at, updated_at) VALUES "
            "(?, ?, 'viewer', 'active', 'owner-a', 1, 1)",
            ("project-a", principal_id),
        )
        conn.commit()
    first = _get_members(client, limit=1)
    assert first.status_code == 200
    assert first.json()["members"][0]["principal_id"] == principal_id
    assert first.json()["next_cursor"] == principal_id
    second = _get_members(client, limit=1, cursor=principal_id)
    assert second.status_code == 200
    assert second.json()["members"][0]["principal_id"] == "directory-user"


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


PROJECT_B_TOKEN = "second-project-service-token-with-32-plus-characters"
READ_ONLY_B_TOKEN = "only-sessions-project-b-token-32-plus-characters"


def _set_multi_scopes(monkeypatch, tmp_path, records):
    path = tmp_path / "management-scopes.json"
    path.write_text(
        json.dumps({"version": 1, "scopes": records}),
        encoding="utf-8",
    )
    path.chmod(0o600)
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_SCOPES_FILE", str(path))
    return path


def _scope(token, project, principal, capabilities=None, instance_id=INSTANCE_ID):
    return {
        "instance_id": instance_id,
        "token": token,
        "principal_id": principal,
        "project_id": project,
        "capabilities": capabilities
        or [
            "session.metadata.read",
            "project.membership.read",
        ],
    }


def test_multiple_project_scopes_do_not_cross_sessions(
    read_client, tmp_path, monkeypatch
):
    client, session_path = read_client
    _set_multi_scopes(
        monkeypatch,
        tmp_path,
        [_scope(PROJECT_B_TOKEN, "project-b", "owner-b")],
    )
    with SessionStore(session_path) as store:
        session = store.create_session(project="project-b", entry_point="web")
        store.bind_identity_context(
            session.session_id, principal_id="owner-b", room_id="secret-room"
        )
        store.append_message(session.session_id, "user", "private-project-b-owner-b")

    monkeypatch.setattr(
        routes_integration,
        "_authorized_project",
        lambda principal, project: (principal, project)
        in {("owner-a", "project-a"), ("owner-b", "project-b")},
    )
    second = _get(client, token=PROJECT_B_TOKEN, project="project-b")
    assert second.status_code == 200
    assert len(second.json()["items"]) == 1
    assert second.json()["items"][0]["id"] == session.session_id
    assert "private-project-b-owner-b" not in second.text
    assert "private-c" not in second.text
    assert _get(client, token=PROJECT_B_TOKEN, project="project-a").status_code == 403
    assert _get(client, token=TOKEN, project="project-b").status_code == 403
    assert len(_get(client, token=TOKEN, project="project-a").json()["items"]) == 1
    assert _get(client, token=MANIFEST_TOKEN).status_code == 401


def test_second_project_members_requires_its_own_explicit_admin(
    members_client, tmp_path, monkeypatch
):
    client, membership_path = members_client
    _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(PROJECT_B_TOKEN, "project-b", "owner-b")]
    )
    with sqlite3.connect(membership_path) as conn:
        conn.execute(
            "INSERT INTO projects(project_id, status, created_at, updated_at) "
            "VALUES ('project-b', 'active', 1, 1)"
        )
        conn.execute(
            "INSERT INTO project_memberships "
            "(project_id, principal_id, role, status, granted_by, "
            "created_at, updated_at) "
            "VALUES ('project-b', 'owner-b', 'admin', 'active', 'manual', 1, 1)"
        )
        conn.execute(
            "INSERT INTO project_memberships "
            "(project_id, principal_id, role, status, granted_by, "
            "created_at, updated_at) "
            "VALUES ('project-b', 'viewer-b', 'viewer', 'active', 'manual', 1, 1)"
        )
    response = _get_members(client, project="project-b", token=PROJECT_B_TOKEN)
    assert response.status_code == 200
    assert response.json()["project_id"] == "project-b"
    assert {x["principal_id"] for x in response.json()["members"]} == {
        "owner-b",
        "viewer-b",
    }
    assert (
        _get_members(client, project="project-a", token=PROJECT_B_TOKEN).status_code
        == 403
    )
    assert _get_members(client, project="project-b", token=TOKEN).status_code == 403
    with sqlite3.connect(membership_path) as conn:
        conn.execute(
            "UPDATE project_memberships SET role = 'viewer' "
            "WHERE project_id = 'project-b' AND principal_id = 'owner-b'"
        )
    assert (
        _get_members(client, project="project-b", token=PROJECT_B_TOKEN).status_code
        == 403
    )
    with sqlite3.connect(membership_path) as conn:
        conn.execute(
            "UPDATE project_memberships SET role = 'admin', "
            "granted_by = 'directory-policy' "
            "WHERE project_id = 'project-b' AND principal_id = 'owner-b'"
        )
    assert (
        _get_members(client, project="project-b", token=PROJECT_B_TOKEN).status_code
        == 403
    )


def test_capability_restriction_is_enforced_per_token(
    read_client, tmp_path, monkeypatch
):
    client, path = read_client
    _set_multi_scopes(
        monkeypatch,
        tmp_path,
        [
            _scope(
                READ_ONLY_B_TOKEN,
                "project-b",
                "owner-b",
                capabilities=["session.metadata.read"],
            )
        ],
    )
    monkeypatch.setattr(routes_integration, "_authorized_project", lambda *_: True)
    response = _get(client, token=READ_ONLY_B_TOKEN, project="project-b")
    assert response.status_code == 200
    assert (
        _get_members(client, project="project-b", token=READ_ONLY_B_TOKEN).status_code
        == 403
    )
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert "project.membership.read" in manifest.json()["capabilities"]
    assert "session.metadata.read" in manifest.json()["capabilities"]


def test_scope_file_can_be_used_without_legacy_credentials(
    read_client, tmp_path, monkeypatch
):
    client, _ = read_client
    for key in (
        "UAGENT_MANAGEMENT_READ_TOKEN",
        "UAGENT_MANAGEMENT_READ_PRINCIPAL",
        "UAGENT_MANAGEMENT_READ_PROJECT_ID",
    ):
        monkeypatch.delenv(key)
    _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(PROJECT_B_TOKEN, "project-a", "owner-a")]
    )
    response = _get(client, token=PROJECT_B_TOKEN)
    assert response.status_code == 200
    assert _get(client, token=TOKEN).status_code == 401
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert "session.metadata.read" in manifest.json()["capabilities"]


def test_scope_file_token_rotation_is_effective_without_restart(
    read_client, tmp_path, monkeypatch
):
    client, _ = read_client
    old_token = PROJECT_B_TOKEN
    new_token = READ_ONLY_B_TOKEN
    file = _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(old_token, "project-a", "owner-a")]
    )
    assert _get(client, token=old_token).status_code == 200
    file.write_text(
        json.dumps(
            {
                "version": 1,
                "scopes": [_scope(new_token, "project-a", "owner-a")],
            }
        ),
        encoding="utf-8",
    )
    assert _get(client, token=old_token).status_code == 401
    assert _get(client, token=new_token).status_code == 200


@pytest.mark.parametrize(
    "records",
    [
        lambda: [_scope(TOKEN, "project-b", "owner-b")],
        lambda: [_scope(PROJECT_B_TOKEN, "project-b", "owner-b", instance_id="other")],
        lambda: [
            _scope(
                PROJECT_B_TOKEN,
                "project-b",
                "owner-b",
                capabilities=["project.membership.write"],
            )
        ],
        lambda: [_scope(PROJECT_B_TOKEN, "project-b", "owner-b")] * 2,
        lambda: [_scope("short", "project-b", "owner-b")],
        lambda: [
            _scope(
                PROJECT_B_TOKEN,
                "project-b",
                "owner-b",
                capabilities=["session.metadata.read", "session.metadata.read"],
            )
        ],
    ],
)
def test_malformed_or_ambiguous_scope_configuration_fails_closed(
    read_client, tmp_path, monkeypatch, records
):
    client, _ = read_client
    _set_multi_scopes(monkeypatch, tmp_path, records())
    assert _get(client).status_code == 503
    assert _get_members(client).status_code == 503
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert manifest.status_code == 200
    assert "session.metadata.read" not in manifest.json()["capabilities"]
    assert "project.membership.read" not in manifest.json()["capabilities"]


def test_absent_scope_file_rejects_all_service_requests(
    read_client, tmp_path, monkeypatch
):
    client, _ = read_client
    monkeypatch.setenv(
        "UAGENT_MANAGEMENT_READ_SCOPES_FILE",
        str(tmp_path / "no-such-scopes-file.json"),
    )
    assert _get(client).status_code == 503
    assert _get_members(client).status_code == 503


def test_scope_file_requires_private_permissions(read_client, tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("Unix permission bits unavailable")
    client, _ = read_client
    path = _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(PROJECT_B_TOKEN, "project-a", "owner-a")]
    )
    path.chmod(0o644)
    assert _get(client, token=PROJECT_B_TOKEN).status_code == 503
    path.chmod(0o600)
    assert _get(client, token=PROJECT_B_TOKEN).status_code == 200


def test_scoped_config_never_exposes_secret_in_errors(
    read_client, tmp_path, monkeypatch
):
    client, _ = read_client
    path = _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(PROJECT_B_TOKEN, "project-b", "owner-b")]
    )
    path.write_text("not-json", encoding="utf-8")
    response = _get(client, token=PROJECT_B_TOKEN, project="project-b")
    assert response.status_code == 503
    assert PROJECT_B_TOKEN not in response.text
    assert str(path) not in response.text


def test_manifest_token_cannot_be_used_as_file_read_token(
    read_client, tmp_path, monkeypatch
):
    client, _ = read_client
    _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(MANIFEST_TOKEN, "project-a", "owner-a")]
    )
    assert _get(client, token=MANIFEST_TOKEN).status_code == 503
    assert _get(client).status_code == 503
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert manifest.status_code == 200
    assert "session.metadata.read" not in manifest.json()["capabilities"]


def test_legacy_read_token_cannot_reuse_manifest_credential(read_client, monkeypatch):
    client, _ = read_client
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_TOKEN", MANIFEST_TOKEN)
    assert _get(client, token=MANIFEST_TOKEN).status_code == 503
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert "session.metadata.read" not in manifest.json()["capabilities"]


def test_scope_file_replacement_during_fd_check_reads_opened_file(
    read_client, tmp_path, monkeypatch
):
    if os.name == "nt":
        pytest.skip("Unix file descriptor swap regression")
    client, _ = read_client
    original = _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(PROJECT_B_TOKEN, "project-a", "owner-a")]
    )
    replacement = tmp_path / "replacement.json"
    replacement.write_text(
        json.dumps(
            {
                "version": 1,
                "scopes": [_scope(READ_ONLY_B_TOKEN, "project-a", "owner-a")],
            }
        ),
        encoding="utf-8",
    )
    replacement.chmod(0o600)
    actual_fstat = os.fstat
    swapped = []

    def swap_after_open(fd):
        if not swapped:
            swapped.append(True)
            os.replace(replacement, original)
        return actual_fstat(fd)

    monkeypatch.setattr(routes_integration.os, "fstat", swap_after_open)
    response = _get(client, token=PROJECT_B_TOKEN)
    assert response.status_code == 200
    assert swapped == [True]
    # Following requests pick up the new file. The in-flight request used
    # the already-open original descriptor, rather than re-opening by path.
    assert _get(client, token=PROJECT_B_TOKEN).status_code == 401
    assert _get(client, token=READ_ONLY_B_TOKEN).status_code == 200


def test_scope_file_rejects_insecure_opened_fd_owner(
    read_client, tmp_path, monkeypatch
):
    if os.name == "nt":
        pytest.skip("Unix owner check")
    client, _ = read_client
    scope_path = _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(PROJECT_B_TOKEN, "project-a", "owner-a")]
    )
    scope_stat = scope_path.stat()
    real_fstat = os.fstat

    def foreign_owned(fd):
        metadata = real_fstat(fd)
        if (metadata.st_dev, metadata.st_ino) != (scope_stat.st_dev, scope_stat.st_ino):
            return metadata

        class FakeStat:
            st_mode = metadata.st_mode
            st_uid = os.geteuid() + 1000001

            def __getattr__(self, name):
                return getattr(metadata, name)

        return FakeStat()

    monkeypatch.setattr(routes_integration.os, "fstat", foreign_owned)
    assert _get(client, token=PROJECT_B_TOKEN).status_code == 503


def test_scope_file_refuses_symlink_even_when_target_is_private(
    read_client, tmp_path, monkeypatch
):
    client, _ = read_client
    actual = _set_multi_scopes(
        monkeypatch, tmp_path, [_scope(PROJECT_B_TOKEN, "project-a", "owner-a")]
    )
    symlink = tmp_path / "scope-symlink.json"
    try:
        symlink.symlink_to(actual)
    except (NotImplementedError, OSError):
        pytest.skip("symlink creation not permitted")
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_SCOPES_FILE", str(symlink))
    assert _get(client, token=PROJECT_B_TOKEN).status_code == 503


class _FakeDacl:
    def __init__(self, aces):
        self.aces = aces

    def GetAceCount(self):
        return len(self.aces)

    def GetAce(self, index):
        return self.aces[index]


def test_windows_dacl_validation_allows_only_trusted_sids():
    allowed = {
        "S-1-5-21-owner",
        "S-1-5-18",
        "S-1-5-32-544",
        "S-1-3-4",  # OWNER RIGHTS resolves to the validated file owner.
    }
    routes_integration._validate_windows_dacl(
        _FakeDacl(
            [
                ((0, 0), 0x1, "S-1-5-21-owner"),
                ((0, 0), 0x1, "S-1-5-18"),
                ((0, 0), 0x1, "S-1-3-4"),
            ]
        ),
        "S-1-5-21-owner",
        allowed,
        str,
    )
    with pytest.raises(ValueError):
        routes_integration._validate_windows_dacl(
            _FakeDacl([((0, 0), 0x1, "S-1-5-32-545")]),
            "S-1-5-21-owner",
            allowed,
            str,
        )
    with pytest.raises(ValueError):
        routes_integration._validate_windows_dacl(
            _FakeDacl([]),
            "S-1-5-21-foreign",
            allowed,
            str,
        )
    with pytest.raises(ValueError):
        routes_integration._validate_windows_dacl(None, "S-1-5-21-owner", allowed, str)
    with pytest.raises(ValueError):
        routes_integration._validate_windows_dacl(
            _FakeDacl([((5, 0), 0x1, "S-1-5-21-owner")]), "S-1-5-21-owner", allowed, str
        )


def test_fifo_scope_file_is_rejected_without_blocking(
    read_client, tmp_path, monkeypatch
):
    if os.name == "nt" or not hasattr(os, "mkfifo"):
        pytest.skip("FIFO regression is Unix-specific")
    client, _ = read_client
    fifo = tmp_path / "read-scopes.fifo"
    os.mkfifo(fifo, 0o600)
    monkeypatch.setenv("UAGENT_MANAGEMENT_READ_SCOPES_FILE", str(fifo))
    real_open = os.open
    seen = []

    def checked_open(path, flags, *args, **kwargs):
        if os.fspath(path) == os.fspath(fifo):
            # Fail immediately rather than block the test on older code.
            assert flags & os.O_NONBLOCK, "FIFO open would block the API"
            seen.append(flags)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(routes_integration.os, "open", checked_open)
    assert _get(client).status_code == 503
    assert _get_members(client).status_code == 503
    manifest = client.get(
        "/api/admin/integration/v1/manifest",
        headers={"Authorization": f"Bearer {MANIFEST_TOKEN}"},
    )
    assert manifest.status_code == 200
    assert "session.metadata.read" not in manifest.json()["capabilities"]
    assert len(seen) == 3

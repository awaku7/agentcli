"""Read-only management session contract and authorization regression tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

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

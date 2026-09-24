from __future__ import annotations

import base64
from contextlib import closing
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from uagent.runtime.identity_context import IdentityContext, IdentityResolutionError
from uagent.runtime.memory_store import MemoryStore
from uagent.runtime.project_access import ProjectAccessPolicy
from uagent.runtime.session_store import SessionStore
from uagent.runtime.session_portability import encrypt, decrypt
from uagent.web_impl import routes_api as api
from uagent.web_impl import routes_portability as routes
from uagent.web_impl.app import app


@pytest.fixture
def web(tmp_path, monkeypatch):
    state = SimpleNamespace(principal="alice", authenticated=True)

    def identity(_):
        if not state.authenticated:
            raise IdentityResolutionError("authentication required")
        return IdentityContext(state.principal, True, "oidc")

    monkeypatch.setattr(api, "_request_identity", identity)
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "demo")
    monkeypatch.setenv("UAGENT_ADMIN_PRINCIPALS", "root")
    monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
    with closing(MemoryStore(tmp_path / "memory.sqlite3")) as memory:
        ProjectAccessPolicy(memory).set_membership("root", "demo", "alice", "viewer")
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        monkeypatch.setattr(api.core, "session_store", store, raising=False)
        yield TestClient(app), store, state, tmp_path


def package():
    return encrypt(
        {
            "format": "uag-session",
            "version": 1,
            "session": {
                "source_session_id": "old-session",
                "created_at": "",
                "entry_point": "cli",
                "project_hint": "forbidden-project",
            },
            "conversation": [{"role": "user", "content": "Resume my work"}],
            "references": {"memory": ["memory:private@1"], "artifacts": []},
        },
        "good",
    )


def import_request(client):
    return client.post(
        "/api/sessions/import",
        json={"package": base64.b64encode(package()).decode(), "passphrase": "good"},
    )


def test_web_roundtrip_and_owner_enforcement(web):
    client, store, identity, _ = web
    response = import_request(client)
    assert response.status_code == 200, response.text
    sid = response.json()["session_id"]
    assert store.get_session(sid)["principal_id"] == "alice"
    exported = client.post(f"/api/sessions/{sid}/export", json={"passphrase": "other"})
    assert exported.status_code == 200
    assert exported.headers["cache-control"] == "no-store"
    assert (
        decrypt(exported.content, "other")["conversation"][0]["content"]
        == "Resume my work"
    )
    identity.principal = "bob"
    assert (
        client.post(
            f"/api/sessions/{sid}/export", json={"passphrase": "good"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/me/private-room", json={"portable_session_id": sid}
        ).status_code
        == 403
    )
    identity.authenticated = False
    assert import_request(client).status_code == 401


def test_web_resume_new_authorized_private_room(web):
    client, store, _, _ = web
    sid = import_request(client).json()["session_id"]
    response = client.post("/api/me/private-room", json={"portable_session_id": sid})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == "demo"
    assert body["session_id"] != sid
    row = store.get_session(body["session_id"])
    assert row["principal_id"] == "alice" and row["room_id"] == body["room_id"]
    room = api.web_manager.get_room(body["room_id"])
    assert room.portable_history == [{"role": "user", "content": "Resume my work"}]
    assert not room.history_initialized
    assert store.get_portable_metadata(body["session_id"])["references"]["memory"] == [
        "memory:private@1"
    ]


def test_revocation_denies_resume_and_export(web):
    client, store, _, path = web
    sid = import_request(client).json()["session_id"]
    resumed = client.post(
        "/api/me/private-room", json={"portable_session_id": sid}
    ).json()
    with closing(MemoryStore(path / "memory.sqlite3")) as memory:
        memory.db.execute(
            "UPDATE project_memberships SET status='revoked' WHERE principal_id='alice'"
        )
        memory.db.commit()
    count = len(store.list_sessions())
    assert (
        client.post(
            "/api/me/private-room", json={"portable_session_id": sid}
        ).status_code
        == 403
    )
    result = client.post(
        f"/api/sessions/{resumed['session_id']}/export", json={"passphrase": "good"}
    )
    assert result.status_code in {401, 403}
    assert len(store.list_sessions()) == count


def test_web_rejects_paths_unknown_fields_wrong_passphrase(web, monkeypatch):
    client, store, _, _ = web
    encoded = base64.b64encode(package()).decode()
    for body in (
        {"path": "../../secret", "passphrase": "good"},
        {"package": encoded, "passphrase": "wrong"},
        {"package": "not base64", "passphrase": "good"},
    ):
        assert client.post("/api/sessions/import", json=body).status_code == 400
    assert store.list_sessions() == []
    monkeypatch.setattr(routes, "MAX_REQUEST", 10)
    assert (
        client.post(
            "/api/sessions/import", json={"package": encoded, "passphrase": "good"}
        ).status_code
        == 400
    )


def test_web_rechecks_owner_after_crypto(web, monkeypatch):
    client, store, identity, _ = web
    sid = import_request(client).json()["session_id"]
    original = routes.encrypt

    def changed(payload, passphrase):
        result = original(payload, passphrase)
        identity.principal = "bob"
        return result

    monkeypatch.setattr(routes, "encrypt", changed)
    assert (
        client.post(
            f"/api/sessions/{sid}/export", json={"passphrase": "good"}
        ).status_code
        == 403
    )


def test_web_rejects_simple_content_type(web):
    client, _, _, _ = web
    assert (
        client.post(
            "/api/sessions/import", content="{}", headers={"content-type": "text/plain"}
        ).status_code
        == 400
    )

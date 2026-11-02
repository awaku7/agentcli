from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from uagent.runtime.browser_identity import BrowserIdentityCookieMiddleware
from uagent.runtime.identity_context import create_identity_resolver


def test_browser_cookie_default_is_stable_per_client_and_isolated_between_clients(
    monkeypatch,
):
    monkeypatch.delenv("UAGENT_IDENTITY_MODE", raising=False)
    monkeypatch.delenv("UAGENT_BROWSER_COOKIE_SECURE", raising=False)

    app = FastAPI()
    app.add_middleware(BrowserIdentityCookieMiddleware)

    @app.get("/whoami")
    def whoami(request: Request):
        identity = create_identity_resolver().resolve(request)
        return {"principal": identity.principal_id, "kind": identity.authn_kind}

    first = TestClient(app)
    second = TestClient(app)
    first_response = first.get("/whoami")
    second_response = second.get("/whoami")

    first_principal = first_response.json()["principal"]
    assert first_response.json()["kind"] == "browser"
    assert second_response.json()["kind"] == "browser"
    assert first_principal.startswith("browser:")
    assert first_response.headers["set-cookie"].startswith("uag_browser_session=")
    assert "httponly" in first_response.headers["set-cookie"].lower()
    assert "samesite=lax" in first_response.headers["set-cookie"].lower()
    assert second_response.json()["principal"] != first_principal
    assert first.get("/whoami").json()["principal"] == first_principal


def test_browser_logout_does_not_remint_a_missing_cookie(monkeypatch):
    from fastapi import FastAPI
    from fastapi.responses import Response

    monkeypatch.delenv("UAGENT_IDENTITY_MODE", raising=False)
    app = FastAPI()
    app.add_middleware(BrowserIdentityCookieMiddleware)

    @app.post("/auth/logout")
    def logout():
        response = Response("ok")
        response.delete_cookie("uag_browser_session", path="/")
        return response

    client = TestClient(app)
    response = client.post("/auth/logout")

    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 1
    assert cookies[0].startswith("uag_browser_session=")
    assert "max-age=0" in cookies[0].lower()
    assert client.cookies.get("uag_browser_session") is None


def test_invalid_cookie_configuration_does_not_crash_middleware(monkeypatch):
    from fastapi import FastAPI

    monkeypatch.delenv("UAGENT_IDENTITY_MODE", raising=False)
    monkeypatch.setenv("UAGENT_BROWSER_SESSION_TTL", "invalid")
    app = FastAPI()
    app.add_middleware(BrowserIdentityCookieMiddleware)

    @app.get("/health")
    def health():
        return {"ok": True}

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert "set-cookie" not in response.headers


def test_browser_cookie_is_signed_and_expires_server_side(monkeypatch):
    from uagent.runtime.browser_identity import _mint_token, valid_browser_session_token

    monkeypatch.setenv("UAGENT_BROWSER_SESSION_TTL", "60")
    token = _mint_token(now=1000)
    assert valid_browser_session_token(token, now=1059) == token
    assert valid_browser_session_token(token, now=1060) == ""
    assert (
        valid_browser_session_token(
            token[:-1] + ("0" if token[-1] != "0" else "1"), now=1001
        )
        == ""
    )


def test_browser_cookie_guest_project_is_private_to_its_principal():
    from uagent.runtime.memory_store import MemoryStore
    from uagent.runtime.project_access import ProjectAccessPolicy

    from uagent.runtime.browser_identity import _mint_token

    first = create_identity_resolver("browser").resolve(
        type("Request", (), {"cookies": {"uag_browser_session": _mint_token()}})()
    )
    second = create_identity_resolver("browser").resolve(
        type("Request", (), {"cookies": {"uag_browser_session": _mint_token()}})()
    )
    first_project = "browser-" + first.principal_id.split(":", 1)[1]
    second_project = "browser-" + second.principal_id.split(":", 1)[1]
    store = MemoryStore(":memory:")
    try:
        policy = ProjectAccessPolicy(store)
        assert policy.can_access(first.principal_id, first_project, "editor")
        assert not policy.can_access(first.principal_id, second_project, "viewer")
        assert not policy.can_access(first.principal_id, first_project, "admin")
    finally:
        store.close()

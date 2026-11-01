"""Web Sandbox startup status is server-wide and authenticated."""

import asyncio
import json
from types import SimpleNamespace

from fastapi.responses import JSONResponse

from uagent.web_impl import routes_api
from uagent.web_impl.rooms import web_manager


def test_sandbox_status_reports_server_startup_not_room_workers(monkeypatch):
    monkeypatch.setattr(
        routes_api,
        "_request_identity",
        lambda _request: SimpleNamespace(principal_id="alice"),
    )
    monkeypatch.setattr(web_manager, "sandbox_enabled", False, raising=False)
    monkeypatch.setattr(web_manager, "sandbox_session_manager", None)

    def get_state():
        response = asyncio.run(routes_api.get_sandbox_status(object()))
        assert isinstance(response, JSONResponse)
        assert response.headers["cache-control"] == "no-store"
        return json.loads(response.body)["state"]

    assert get_state() == "OFF"
    monkeypatch.setattr(web_manager, "sandbox_enabled", True)
    assert get_state() == "UNKNOWN"
    monkeypatch.setattr(web_manager, "sandbox_session_manager", object())
    assert get_state() == "ON"


def test_sandbox_status_requires_authentication(monkeypatch):
    from uagent.runtime.identity_context import IdentityResolutionError

    def reject(_request):
        raise IdentityResolutionError("not authenticated")

    monkeypatch.setattr(routes_api, "_request_identity", reject)
    response = asyncio.run(routes_api.get_sandbox_status(object()))
    assert response.status_code == 401

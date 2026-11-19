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


def test_sandbox_init_runs_on_real_console_streams(monkeypatch):
    import io as _io
    import sys

    from uagent.web_impl import init as web_init

    capture_out, capture_err = _io.StringIO(), _io.StringIO()
    real_out, real_err = _io.StringIO(), _io.StringIO()
    seen = {}

    def fake_inner(parser, *, sandbox_mode):
        seen["stdout"] = sys.stdout
        seen["stderr"] = sys.stderr
        return "manager"

    monkeypatch.setattr(web_init, "_initialize_web_sandbox_on_console", fake_inner)
    monkeypatch.setattr(sys, "stdout", capture_out)
    monkeypatch.setattr(sys, "stderr", capture_err)
    monkeypatch.setattr(sys, "__stdout__", real_out)
    monkeypatch.setattr(sys, "__stderr__", real_err)

    assert web_init._initialize_web_sandbox(object(), sandbox_mode="mxc") == "manager"
    # Inside, the prompt and errors go to the real console, not the
    # Web UI capture streams installed at import time.
    assert seen["stdout"] is real_out
    assert seen["stderr"] is real_err
    # And the capture streams are restored afterwards.
    assert sys.stdout is capture_out
    assert sys.stderr is capture_err


def test_real_console_streams_restored_on_error(monkeypatch):
    import io as _io
    import sys

    import pytest

    from uagent.web_impl import init as web_init

    capture_out = _io.StringIO()
    monkeypatch.setattr(sys, "stdout", capture_out)
    monkeypatch.setattr(sys, "__stdout__", _io.StringIO())
    with pytest.raises(RuntimeError):
        with web_init._real_console_streams():
            assert sys.stdout is not capture_out
            raise RuntimeError("boom")
    assert sys.stdout is capture_out

from __future__ import annotations

import asyncio

import pytest

from uagent.runtime.auth_management import authentication_configuration_fingerprint
from uagent.runtime.identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
)
from uagent.runtime.web_origin_policy import (
    configured_websocket_origins,
    validate_websocket_origin,
)
from uagent.web_impl import routes_ws


class _Request:
    def __init__(self, origin: str | None):
        self.headers = {} if origin is None else {"origin": origin}


def test_local_websocket_origin_defaults_are_loopback_only(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")
    monkeypatch.delenv("UAGENT_WEB_ALLOWED_ORIGINS", raising=False)

    localhost = validate_websocket_origin(_Request("http://localhost:8000"))
    ipv4 = validate_websocket_origin(_Request("http://127.0.0.1:8000"))
    ipv6 = validate_websocket_origin(_Request("http://[::1]:8000"))

    assert localhost == "http://localhost:8000"
    assert ipv4 == "http://127.0.0.1:8000"
    assert ipv6 == "http://[::1]:8000"

    with pytest.raises(IdentityResolutionError, match="not allowed"):
        validate_websocket_origin(_Request("https://evil.example"))


def test_non_local_websocket_origin_requires_explicit_allowlist(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "trusted_proxy")
    monkeypatch.delenv("UAGENT_WEB_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(IdentityConfigurationError, match="required"):
        configured_websocket_origins()

    with pytest.raises(IdentityConfigurationError, match="required"):
        validate_websocket_origin(_Request("https://uag.corp.example"))


def test_explicit_websocket_origin_allowlist_is_exact(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "trusted_proxy")
    monkeypatch.setenv(
        "UAGENT_WEB_ALLOWED_ORIGINS",
        "https://uag.corp.example,https://admin.corp.example:8443/",
    )

    assert (
        validate_websocket_origin(_Request("https://uag.corp.example"))
        == "https://uag.corp.example"
    )
    assert (
        validate_websocket_origin(_Request("https://admin.corp.example:8443"))
        == "https://admin.corp.example:8443"
    )

    with pytest.raises(IdentityResolutionError, match="not allowed"):
        validate_websocket_origin(_Request("https://evil.example"))
    with pytest.raises(IdentityResolutionError, match="not allowed"):
        validate_websocket_origin(_Request("http://uag.corp.example"))


@pytest.mark.parametrize("origin", [None, "", "null", "file://local", "https://a/b"])
def test_websocket_origin_rejects_missing_opaque_or_malformed(monkeypatch, origin):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")
    monkeypatch.delenv("UAGENT_WEB_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(IdentityResolutionError):
        validate_websocket_origin(_Request(origin))


def test_invalid_configured_origin_fails_closed(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "trusted_proxy")
    monkeypatch.setenv("UAGENT_WEB_ALLOWED_ORIGINS", "https://uag.example/path")

    with pytest.raises(IdentityConfigurationError, match="invalid origin"):
        configured_websocket_origins()


def test_websocket_route_rejects_origin_before_identity_resolution(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")
    monkeypatch.delenv("UAGENT_WEB_ALLOWED_ORIGINS", raising=False)

    def should_not_run(*args, **kwargs):
        raise AssertionError("identity resolution must not run for a rejected Origin")

    monkeypatch.setattr(routes_ws, "resolve_web_connection", should_not_run)

    class Socket:
        headers = {"origin": "https://evil.example"}
        query_params = {"room": "shared"}

        def __init__(self):
            self.closed = []

        async def close(self, code):
            self.closed.append(code)

    socket = Socket()
    asyncio.run(routes_ws.websocket_endpoint(socket))

    assert socket.closed == [1008]


def test_websocket_origin_policy_updates_authentication_fingerprint(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "local")
    monkeypatch.delenv("UAGENT_WEB_ALLOWED_ORIGINS", raising=False)
    before = authentication_configuration_fingerprint()

    monkeypatch.setenv(
        "UAGENT_WEB_ALLOWED_ORIGINS",
        "https://uag.example",
    )

    assert authentication_configuration_fingerprint() != before

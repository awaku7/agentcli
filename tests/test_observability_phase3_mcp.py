from __future__ import annotations

import asyncio

import httpx

from uagent.tools.mcp.client import MCPClient
from uagent.tools.mcp.http_client import create_mcp_http_client
from uagent.tools.mcp.stateless_transport import StatelessHTTPClient

_TRACEPARENT = "00-11111111111111111111111111111111-2222222222222222-01"


class _PropagationBackend:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def inject_context(self, carrier: dict[str, str]) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("propagation unavailable")
        carrier["traceparent"] = _TRACEPARENT
        carrier["tracestate"] = "uag=test"
        carrier["baggage"] = "secret=must-not-propagate"


async def _run_request_hooks(client: httpx.AsyncClient, request: httpx.Request) -> None:
    for hook in client.event_hooks.get("request", []):
        await hook(request)


def test_mcp_http_trace_propagation_is_opt_in() -> None:
    client = create_mcp_http_client()
    try:
        assert client.event_hooks.get("request", []) == []
    finally:
        asyncio.run(client.aclose())


def test_trusted_mcp_http_injection_preserves_auth_and_omits_baggage(
    monkeypatch,
) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    client = create_mcp_http_client(
        headers={
            "Authorization": "Bearer keep-me",
            "traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
            "tracestate": "spoof=1",
            "baggage": "configured=secret",
        },
        trusted_trace_propagation=True,
    )
    request = httpx.Request("POST", "https://mcp.example/mcp", headers=client.headers)
    try:
        asyncio.run(_run_request_hooks(client, request))
        assert backend.calls == 1
        assert request.headers["Authorization"] == "Bearer keep-me"
        assert request.headers["traceparent"] == _TRACEPARENT
        assert request.headers["tracestate"] == "uag=test"
        assert "baggage" not in request.headers
    finally:
        asyncio.run(client.aclose())


def test_trusted_mcp_http_injection_failure_is_isolated(monkeypatch) -> None:
    backend = _PropagationBackend(fail=True)
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    client = create_mcp_http_client(
        headers={
            "Authorization": "Bearer keep-me",
            "traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
            "tracestate": "spoof=1",
            "baggage": "configured=secret",
        },
        trusted_trace_propagation=True,
    )
    request = httpx.Request("POST", "https://mcp.example/mcp", headers=client.headers)
    try:
        asyncio.run(_run_request_hooks(client, request))
        assert backend.calls == 1
        assert request.headers["Authorization"] == "Bearer keep-me"
        assert "traceparent" not in request.headers
        assert "tracestate" not in request.headers
        assert "baggage" not in request.headers
    finally:
        asyncio.run(client.aclose())


def test_stateless_transport_uses_uag_owned_trusted_http_client() -> None:
    async def scenario() -> None:
        transport = StatelessHTTPClient(
            "https://mcp.example/mcp", trusted_trace_propagation=True
        )
        await transport.__aenter__()
        try:
            assert transport.http_client is not None
            assert len(transport.http_client.event_hooks.get("request", [])) == 1
        finally:
            await transport.__aexit__(None, None, None)

    asyncio.run(scenario())


def test_stateful_setup_failure_closes_owned_trace_http_client(monkeypatch) -> None:
    class _OwnedClient:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    owned = _OwnedClient()

    def fake_create(*args, **kwargs):
        assert kwargs.get("trusted_trace_propagation") is True
        return owned

    class _FailingTransport:
        async def __aenter__(self):
            raise RuntimeError("transport setup failed")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    def fake_streamable_http_client(*args, **kwargs):
        assert kwargs.get("http_client") is owned
        return _FailingTransport()

    monkeypatch.setattr("uagent.tools.mcp.client.create_mcp_http_client", fake_create)
    monkeypatch.setattr(
        "uagent.tools.mcp.client.streamable_http_client",
        fake_streamable_http_client,
    )

    from uagent.tools.mcp.client import MCPClient
    from uagent.tools.mcp.errors import MCPTransportError

    async def scenario() -> None:
        client = MCPClient(
            url="https://mcp.example/mcp",
            trusted_trace_propagation=True,
            protocol_mode="legacy",
        )
        try:
            await client.__aenter__()
        except MCPTransportError:
            pass
        else:
            raise AssertionError("expected MCPTransportError")
        assert owned.closed is True
        assert client._http_client is None

    asyncio.run(scenario())


def test_stateful_setup_cancellation_closes_owned_trace_http_client(
    monkeypatch,
) -> None:
    class _OwnedClient:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    owned = _OwnedClient()

    def fake_create(*args, **kwargs):
        assert kwargs.get("trusted_trace_propagation") is True
        return owned

    class _CancelledTransport:
        async def __aenter__(self):
            raise asyncio.CancelledError()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    def fake_streamable_http_client(*args, **kwargs):
        assert kwargs.get("http_client") is owned
        return _CancelledTransport()

    monkeypatch.setattr("uagent.tools.mcp.client.create_mcp_http_client", fake_create)
    monkeypatch.setattr(
        "uagent.tools.mcp.client.streamable_http_client",
        fake_streamable_http_client,
    )

    from uagent.tools.mcp.client import MCPClient

    async def scenario() -> None:
        client = MCPClient(
            url="https://mcp.example/mcp",
            trusted_trace_propagation=True,
            protocol_mode="legacy",
        )
        try:
            await client.__aenter__()
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("expected CancelledError")
        assert owned.closed is True
        assert client._http_client is None

    asyncio.run(scenario())


def test_trusted_mcp_sdk_call_injects_message_trace_meta(monkeypatch) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    seen: dict[str, object] = {}

    class Session:
        async def call_tool(self, name, arguments, *, meta=None):
            seen["name"] = name
            seen["arguments"] = arguments
            seen["meta"] = meta
            return {"ok": True}

    client = MCPClient(trusted_trace_propagation=True)
    client.session = Session()
    result = asyncio.run(client.call_tool("ping", {"value": 1}))

    assert result == {"ok": True}
    assert seen["meta"] == {
        "traceparent": _TRACEPARENT,
        "tracestate": "uag=test",
    }


def test_trusted_mcp_sdk_list_uses_paginated_params_meta(monkeypatch) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    seen: dict[str, object] = {}

    class Session:
        async def list_tools(self, *, params=None):
            seen["params"] = params
            return {"tools": []}

    client = MCPClient(trusted_trace_propagation=True)
    client.session = Session()
    result = asyncio.run(client.list_tools())

    assert result == {"tools": []}
    params = seen["params"]
    assert params is not None
    assert params.meta == {
        "traceparent": _TRACEPARENT,
        "tracestate": "uag=test",
    }


def test_trusted_mcp_sdk_call_keeps_legacy_sdk_compatible(monkeypatch) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    calls = []

    class LegacySession:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"ok": True}

    client = MCPClient(trusted_trace_propagation=True)
    client.session = LegacySession()
    result = asyncio.run(client.call_tool("ping", {"value": 1}))

    assert result == {"ok": True}
    assert calls == [("ping", {"value": 1})]


def test_trusted_stateless_mcp_injects_trace_meta_into_jsonrpc(monkeypatch) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    seen: dict[str, object] = {}

    class Response:
        status_code = 200

        def json(self):
            return {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}

    class HTTPClient:
        async def post(self, url, *, json, headers):
            seen["url"] = url
            seen["json"] = json
            seen["headers"] = headers
            return Response()

    transport = StatelessHTTPClient(
        "https://mcp.example/mcp",
        http_client=HTTPClient(),
        trusted_trace_propagation=True,
    )
    result = asyncio.run(transport.call_tool("ping", {"value": 1}))

    assert result["result"] == {"ok": True}
    body = seen["json"]
    assert isinstance(body, dict)
    assert body["params"]["_meta"] == {
        "traceparent": _TRACEPARENT,
        "tracestate": "uag=test",
    }
    assert "baggage" not in body["params"]["_meta"]

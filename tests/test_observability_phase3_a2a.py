from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from uagent.a2a.auth import require_bearer_auth
from uagent.a2a.client import A2AClient
from uagent.a2a.errors import A2AHttpError
from uagent.runtime.observability.otel_backend import OpenTelemetryBackend
from uagent.runtime.observability.settings import ObservabilitySettings


class _PropagationBackend:
    enabled = True

    def __init__(self) -> None:
        self.injected = 0
        self.attached: list[dict[str, str]] = []
        self.entered = 0
        self.exited = 0

    def inject_context(self, carrier: dict[str, str]) -> None:
        self.injected += 1
        carrier["traceparent"] = (
            "00-11111111111111111111111111111111-2222222222222222-01"
        )
        carrier["tracestate"] = "vendor=value"

    @contextmanager
    def attach_remote_context(self, carrier: dict[str, str]):
        self.attached.append(dict(carrier))
        self.entered += 1
        try:
            yield None
        finally:
            self.exited += 1


def _request(headers: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(credential_store=None)),
        headers=headers,
    )


def test_a2a_client_injects_trace_context_only_with_bearer_token(monkeypatch) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr("uagent.a2a.client.get_observability_backend", lambda: backend)

    client = A2AClient(base_url="http://a2a.example", token="secret")
    try:
        headers = client._auth_headers()
    finally:
        client.close()

    assert headers["Authorization"] == "Bearer secret"
    assert headers["traceparent"].startswith("00-")
    assert headers["tracestate"] == "vendor=value"
    assert backend.injected == 1

    client = A2AClient(base_url="http://a2a.example", token=" ")
    try:
        assert client._auth_headers() == {}
    finally:
        client.close()
    assert backend.injected == 1


def test_a2a_auth_attaches_trace_context_only_after_authentication(monkeypatch) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.a2a.auth.resolve_credential_secret",
        lambda *args, **kwargs: "secret",
    )
    monkeypatch.setattr("uagent.a2a.auth.get_observability_backend", lambda: backend)
    request = _request(
        {
            "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
            "tracestate": "vendor=value",
            "baggage": "principal_id=should-not-propagate",
        }
    )

    async def consume() -> None:
        dependency = require_bearer_auth(request, authorization="Bearer secret")
        assert await dependency.__anext__() == {
            "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
            "tracestate": "vendor=value",
        }
        with pytest.raises(StopAsyncIteration):
            await dependency.__anext__()

    asyncio.run(consume())

    assert backend.attached == [
        {
            "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
            "tracestate": "vendor=value",
        }
    ]
    assert backend.entered == 1
    assert backend.exited == 1


def test_a2a_auth_credential_lookup_runs_off_event_loop(monkeypatch) -> None:
    backend = _PropagationBackend()
    event_loop_thread = threading.get_ident()
    lookup_threads: list[int] = []

    def resolve(*args, **kwargs):
        lookup_threads.append(threading.get_ident())
        return "secret"

    monkeypatch.setattr("uagent.a2a.auth.resolve_credential_secret", resolve)
    monkeypatch.setattr("uagent.a2a.auth.get_observability_backend", lambda: backend)
    request = _request({})

    async def consume() -> None:
        dependency = require_bearer_auth(request, authorization="Bearer secret")
        assert await dependency.__anext__() == {}
        with pytest.raises(StopAsyncIteration):
            await dependency.__anext__()

    asyncio.run(consume())

    assert lookup_threads
    assert all(thread_id != event_loop_thread for thread_id in lookup_threads)


def test_a2a_auth_rejects_before_trace_context_is_attached(monkeypatch) -> None:
    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.a2a.auth.resolve_credential_secret",
        lambda *args, **kwargs: "secret",
    )
    monkeypatch.setattr("uagent.a2a.auth.get_observability_backend", lambda: backend)
    request = _request(
        {"traceparent": "00-11111111111111111111111111111111-2222222222222222-01"}
    )

    async def consume_invalid() -> None:
        dependency = require_bearer_auth(request, authorization="Bearer wrong")
        await dependency.__anext__()

    with pytest.raises(A2AHttpError):
        asyncio.run(consume_invalid())
    assert backend.attached == []
    assert backend.entered == 0


def test_a2a_stream_reattaches_trusted_context_inside_generator(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from uagent.a2a.server import build_app

    backend = _PropagationBackend()
    monkeypatch.setattr(
        "uagent.a2a.auth.resolve_credential_secret",
        lambda *args, **kwargs: "secret",
    )
    monkeypatch.setattr("uagent.a2a.auth.get_observability_backend", lambda: backend)
    monkeypatch.setattr("uagent.a2a.server.get_observability_backend", lambda: backend)

    app = build_app(credential_store=SimpleNamespace())
    response = TestClient(app).post(
        "/message:stream",
        json={
            "message": {"role": "user", "content": "hello"},
            "returnImmediately": False,
        },
        headers={
            "Authorization": "Bearer secret",
            "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
            "tracestate": "vendor=value",
        },
    )

    assert response.status_code == 200
    trusted = {
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "tracestate": "vendor=value",
    }
    assert backend.attached.count(trusted) == 2
    assert backend.entered == 2
    assert backend.exited == 2


def test_otel_backend_round_trips_w3c_trace_context_without_baggage() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    backend = OpenTelemetryBackend(
        tracer=provider.get_tracer("uag.test.phase3"),
        provider=provider,
        settings=ObservabilitySettings(enabled=True),
    )
    try:
        with backend.start_span("invoke_agent"):
            local_ids = backend.current_trace_ids()
            carrier: dict[str, str] = {}
            backend.inject_context(carrier)

        assert local_ids.trace_id
        assert local_ids.span_id
        assert "traceparent" in carrier
        assert "baggage" not in carrier
        assert set(carrier).issubset({"traceparent", "tracestate"})

        with backend.attach_remote_context(carrier):
            remote_ids = backend.current_trace_ids()
        assert remote_ids.trace_id == local_ids.trace_id
        assert remote_ids.span_id == local_ids.span_id
    finally:
        backend.shutdown()


def test_malformed_remote_context_does_not_replace_current_parent() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    backend = OpenTelemetryBackend(
        tracer=provider.get_tracer("uag.test.phase3.invalid"),
        provider=provider,
        settings=ObservabilitySettings(enabled=True),
    )
    try:
        with backend.start_span("invoke_agent"):
            before = backend.current_trace_ids()
            with backend.attach_remote_context({"traceparent": "not-valid"}):
                during = backend.current_trace_ids()
            assert during == before
    finally:
        backend.shutdown()


def test_malformed_remote_context_preserves_endpoint_exception() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    backend = OpenTelemetryBackend(
        tracer=provider.get_tracer("uag.test.phase3.invalid.exception"),
        provider=provider,
        settings=ObservabilitySettings(enabled=True),
    )
    try:
        with pytest.raises(ValueError, match="endpoint failed"):
            with backend.attach_remote_context({"traceparent": "not-valid"}):
                raise ValueError("endpoint failed")
    finally:
        backend.shutdown()

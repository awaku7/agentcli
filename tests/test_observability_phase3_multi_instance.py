from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from uagent.a2a import auth as a2a_auth
from uagent.a2a import client as a2a_client
from uagent.a2a.auth import require_bearer_auth
from uagent.a2a.client import A2AClient
from uagent.runtime.execution import lifecycle_execution
from uagent.runtime.observability import bootstrap as observability_bootstrap
from uagent.runtime.observability.otel_backend import OpenTelemetryBackend
from uagent.runtime.observability.settings import ObservabilitySettings


def _request(headers: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(credential_store=None)),
        headers=headers,
    )


def _backend(name: str):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    backend = OpenTelemetryBackend(
        tracer=provider.get_tracer(name),
        provider=provider,
        settings=ObservabilitySettings(enabled=True),
    )
    return backend, exporter


def test_a2a_three_instance_trace_chain_preserves_parentage_without_duplicates(
    monkeypatch,
) -> None:
    backend_a, exporter_a = _backend("uag.test.phase3.instance-a")
    backend_b, exporter_b = _backend("uag.test.phase3.instance-b")
    backend_c, exporter_c = _backend("uag.test.phase3.instance-c")

    monkeypatch.setattr(
        a2a_auth,
        "resolve_credential_secret",
        lambda *args, **kwargs: "secret",
    )

    try:
        monkeypatch.setattr(a2a_client, "get_observability_backend", lambda: backend_a)
        client_a = A2AClient(base_url="http://instance-b.example", token="secret")
        try:
            with backend_a.start_span(
                "invoke_agent", attributes={"uag.agent.name": "instance-a"}
            ):
                ids_a = backend_a.current_trace_ids()
                headers_ab = client_a._auth_headers()
        finally:
            client_a.close()

        assert headers_ab["Authorization"] == "Bearer secret"
        assert headers_ab["traceparent"].startswith("00-")
        assert "baggage" not in headers_ab

        async def run_remote_hops():
            monkeypatch.setattr(
                a2a_auth, "get_observability_backend", lambda: backend_b
            )
            dependency_b = require_bearer_auth(
                _request(headers_ab), authorization=headers_ab["Authorization"]
            )
            carrier_b = await dependency_b.__anext__()
            assert carrier_b == {"traceparent": headers_ab["traceparent"]}

            try:
                monkeypatch.setattr(
                    observability_bootstrap,
                    "get_observability_backend",
                    lambda: backend_b,
                )
                with lifecycle_execution():
                    ids_b = backend_b.current_trace_ids()
                    monkeypatch.setattr(
                        a2a_client,
                        "get_observability_backend",
                        lambda: backend_b,
                    )
                    client_b = A2AClient(
                        base_url="http://instance-c.example", token="secret"
                    )
                    try:
                        headers_bc = client_b._auth_headers()
                    finally:
                        client_b.close()
            finally:
                with pytest.raises(StopAsyncIteration):
                    await dependency_b.__anext__()

            assert headers_bc["Authorization"] == "Bearer secret"
            assert headers_bc["traceparent"].startswith("00-")
            assert "baggage" not in headers_bc

            monkeypatch.setattr(
                a2a_auth, "get_observability_backend", lambda: backend_c
            )
            dependency_c = require_bearer_auth(
                _request(headers_bc), authorization=headers_bc["Authorization"]
            )
            carrier_c = await dependency_c.__anext__()
            assert carrier_c == {"traceparent": headers_bc["traceparent"]}

            try:
                monkeypatch.setattr(
                    observability_bootstrap,
                    "get_observability_backend",
                    lambda: backend_c,
                )
                with lifecycle_execution():
                    ids_c = backend_c.current_trace_ids()
            finally:
                with pytest.raises(StopAsyncIteration):
                    await dependency_c.__anext__()

            return ids_b, ids_c

        ids_b, ids_c = asyncio.run(run_remote_hops())

        assert ids_a.trace_id
        assert ids_a.trace_id == ids_b.trace_id == ids_c.trace_id

        spans_a = list(exporter_a.get_finished_spans())
        spans_b = list(exporter_b.get_finished_spans())
        spans_c = list(exporter_c.get_finished_spans())

        assert [span.name for span in spans_a] == ["invoke_agent instance-a"]
        assert [span.name for span in spans_b] == ["invoke_agent uag"]
        assert [span.name for span in spans_c] == ["invoke_agent uag"]

        span_a = spans_a[0]
        span_b = spans_b[0]
        span_c = spans_c[0]

        assert span_a.parent is None
        assert span_b.parent is not None
        assert span_c.parent is not None
        assert span_b.context.trace_id == span_a.context.trace_id
        assert span_c.context.trace_id == span_a.context.trace_id
        assert span_b.parent.span_id == span_a.context.span_id
        assert span_c.parent.span_id == span_b.context.span_id
    finally:
        backend_a.shutdown()
        backend_b.shutdown()
        backend_c.shutdown()

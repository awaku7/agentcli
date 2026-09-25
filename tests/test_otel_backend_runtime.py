from __future__ import annotations

import pytest

from uagent.runtime.observability.settings import ObservabilitySettings


def test_otel_backend_preserves_hierarchy_and_can_force_fresh_root(monkeypatch) -> None:
    pytest.importorskip("opentelemetry.sdk")
    from uagent.runtime.observability.otel_backend import create_otel_backend

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    backend = create_otel_backend(ObservabilitySettings(enabled=True))
    try:
        with backend.start_span(
            "invoke_agent", attributes={"uag.agent.name": "uag"}
        ):
            parent = backend.current_trace_ids()
            assert parent.trace_id is not None
            assert parent.span_id is not None

            with backend.start_span(
                "chat",
                attributes={
                    "uag.llm.provider": "fake",
                    "uag.llm.model": "fake-model",
                },
            ):
                child = backend.current_trace_ids()
                assert child.trace_id == parent.trace_id
                assert child.span_id != parent.span_id

            with backend.start_span(
                "invoke_agent",
                attributes={"uag.agent.name": "uag"},
                root=True,
            ):
                detached = backend.current_trace_ids()
                assert detached.trace_id != parent.trace_id
                assert detached.span_id != parent.span_id
    finally:
        backend.shutdown()

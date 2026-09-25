from __future__ import annotations

import pytest

from uagent.runtime.observability.settings import ObservabilitySettings


def test_otel_backend_preserves_hierarchy_and_can_force_fresh_root(monkeypatch) -> None:
    pytest.importorskip("opentelemetry.sdk")
    from uagent.runtime.observability.otel_backend import create_otel_backend

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    backend = create_otel_backend(ObservabilitySettings(enabled=True))
    try:
        with backend.start_span("invoke_agent", attributes={"uag.agent.name": "uag"}):
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


def test_otel_backend_preserves_explicit_cancelled_status_on_unwind() -> None:
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.trace import StatusCode

    from uagent.runtime.observability.otel_backend import OpenTelemetryBackend

    class CancelSignal(Exception):
        pass

    class RawSpan:
        def __init__(self) -> None:
            self.statuses = []
            self.events = []

        def set_status(self, status) -> None:
            self.statuses.append(status)

        def add_event(self, name, attributes=None) -> None:
            self.events.append((name, dict(attributes or {})))

        def set_attribute(self, name, value) -> None:
            return None

    class Manager:
        def __init__(self, span: RawSpan) -> None:
            self.span = span
            self.exit_args = None

        def __enter__(self):
            return self.span

        def __exit__(self, exc_type, exc, traceback) -> None:
            self.exit_args = (exc_type, exc, traceback)

    class Tracer:
        def __init__(self) -> None:
            self.spans = []
            self.managers = []

        def start_as_current_span(self, *args, **kwargs):
            span = RawSpan()
            manager = Manager(span)
            self.spans.append(span)
            self.managers.append(manager)
            return manager

    class Provider:
        def shutdown(self) -> None:
            return None

    tracer = Tracer()
    backend = OpenTelemetryBackend(
        tracer=tracer,
        provider=Provider(),
        settings=ObservabilitySettings(enabled=True),
    )

    with pytest.raises(CancelSignal):
        with backend.start_span("invoke_agent") as span:
            span.set_status("unset", "cancelled")
            raise CancelSignal("stop")

    raw_span = tracer.spans[0]
    assert raw_span.statuses[-1].status_code == StatusCode.UNSET
    assert raw_span.events == []
    assert tracer.managers[0].exit_args[0] is CancelSignal


def test_otel_backend_still_records_non_cancel_failure_on_unwind() -> None:
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.trace import StatusCode

    from uagent.runtime.observability.otel_backend import OpenTelemetryBackend

    class RawSpan:
        def __init__(self) -> None:
            self.statuses = []
            self.events = []

        def set_status(self, status) -> None:
            self.statuses.append(status)

        def add_event(self, name, attributes=None) -> None:
            self.events.append((name, dict(attributes or {})))

        def set_attribute(self, name, value) -> None:
            return None

    class Manager:
        def __init__(self, span: RawSpan) -> None:
            self.span = span

        def __enter__(self):
            return self.span

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

    class Tracer:
        def __init__(self) -> None:
            self.spans = []

        def start_as_current_span(self, *args, **kwargs):
            span = RawSpan()
            self.spans.append(span)
            return Manager(span)

    class Provider:
        def shutdown(self) -> None:
            return None

    tracer = Tracer()
    backend = OpenTelemetryBackend(
        tracer=tracer,
        provider=Provider(),
        settings=ObservabilitySettings(enabled=True),
    )

    with pytest.raises(RuntimeError):
        with backend.start_span("invoke_agent"):
            raise RuntimeError("secret failure text")

    raw_span = tracer.spans[0]
    assert raw_span.statuses[-1].status_code == StatusCode.ERROR
    assert raw_span.events == [
        (
            "exception",
            {"exception.type": "builtins.RuntimeError"},
        )
    ]

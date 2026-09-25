from __future__ import annotations

from contextlib import contextmanager

from uagent.runtime.context_manager import ContextManager
from uagent.runtime.context_policy import ContextPolicy
from uagent.runtime.context_retrieval import retrieve_candidates
from uagent.runtime.observability.api import TraceIds
from uagent.runtime.observability.decision_log import record_persisted_decision_batch
from uagent.runtime.observability.noop import NOOP_BACKEND
from uagent.runtime.observability.otel_backend import (
    OpenTelemetryBackend,
    _build_metric_exporter,
    _sanitize_metric_attributes,
)
from uagent.runtime.observability.settings import ObservabilitySettings


class _Span:
    def __init__(self) -> None:
        self.attributes = {}
        self.events = []
        self.status = None

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def add_event(self, name, attributes=None) -> None:
        self.events.append((name, dict(attributes or {})))

    def record_exception(self, exc) -> None:
        return None

    def set_status(self, status, description=None) -> None:
        self.status = (status, description)


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.spans = []
        self.events = []
        self.counters = []
        self.histograms = []

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        span = _Span()
        self.spans.append((operation, dict(attributes or {}), root, span))
        yield span

    def record_event(self, name, attributes=None) -> None:
        self.events.append((name, dict(attributes or {})))

    def record_counter(self, name, value=1, attributes=None) -> None:
        self.counters.append((name, value, dict(attributes or {})))

    def record_histogram(self, name, value, attributes=None) -> None:
        self.histograms.append((name, value, dict(attributes or {})))

    def current_trace_ids(self) -> TraceIds:
        return TraceIds(trace_id="1" * 32, span_id="2" * 16)


def test_noop_backend_accepts_metric_calls() -> None:
    NOOP_BACKEND.record_counter("uag.test", 1, {"principal_id": "secret"})
    NOOP_BACKEND.record_histogram("uag.test", 1.5, {"session_id": "secret"})


def test_metric_attributes_are_low_cardinality() -> None:
    safe = _sanitize_metric_attributes(
        {
            "uag.context.kind": "messages",
            "uag.context.decision.action": "KEEP",
            "uag.retrieval.kind": "memory",
            "uag.memory.identity_bound": True,
            "principal_id": "alice",
            "session_id": "session-1",
            "uag.context.user_value": "arbitrary",
        }
    )
    assert safe == {
        "uag.context.kind": "messages",
        "uag.context.decision.action": "KEEP",
        "uag.retrieval.kind": "memory",
        "uag.memory.identity_bound": True,
    }


def test_context_build_emits_aggregate_only_observability(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.context_manager.get_observability_backend", lambda: backend
    )
    manager = ContextManager(policy=ContextPolicy(budget_chars=1000))
    active = manager.build_message_context(
        [{"role": "user", "content": "private prompt body"}]
    )

    assert active.messages
    operation, attributes, _, span = backend.spans[-1]
    assert operation == "uag.context.build"
    assert attributes["uag.context.kind"] == "messages"
    exported = repr((attributes, span.attributes, backend.histograms))
    assert "private prompt body" not in exported
    assert any(name == "uag.context.raw.chars" for name, _, _ in backend.histograms)


def test_context_retrieval_does_not_export_query_or_record_content(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.context_retrieval.get_observability_backend", lambda: backend
    )
    candidates = retrieve_candidates(
        [
            {
                "item_id": "private-record-id",
                "content": "secret record body",
                "summary": "secret summary",
            }
        ],
        query="secret query text",
        max_candidates=1,
    )

    assert len(candidates) == 1
    operation, attributes, _, span = backend.spans[-1]
    assert operation == "retrieval"
    exported = repr((attributes, span.attributes, backend.histograms))
    assert "secret query text" not in exported
    assert "secret record body" not in exported
    assert "private-record-id" not in exported


def test_decision_log_linkage_is_metadata_only(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.observability.decision_log.get_observability_backend",
        lambda: backend,
    )
    record_persisted_decision_batch(
        [
            {
                "action": "KEEP",
                "item_id": "private-item-id",
                "reason": "private decision reason",
                "reference": "private-reference",
            },
            {"action": "EXCLUDE", "reason": "another private reason"},
        ]
    )

    name, attributes = backend.events[-1]
    assert name == "uag.context.decision_batch.persisted"
    assert attributes["uag.context.decision_batch.count"] == 2
    assert attributes["uag.context.decision_batch.keep"] == 1
    assert attributes["uag.context.decision_batch.exclude"] == 1
    assert attributes["uag.trace_id"] == "1" * 32
    assert attributes["uag.span_id"] == "2" * 16
    exported = repr(attributes)
    assert "private-item-id" not in exported
    assert "private decision reason" not in exported
    assert "private-reference" not in exported


def test_metrics_exporter_none_is_independent_from_tracing(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "none")
    assert _build_metric_exporter() is None


def test_metric_recording_failure_is_isolated() -> None:
    class BrokenMeter:
        def create_counter(self, _name):
            raise RuntimeError("metric failure")

        def create_histogram(self, _name):
            raise RuntimeError("metric failure")

    backend = OpenTelemetryBackend(
        tracer=object(),
        provider=object(),
        settings=ObservabilitySettings(enabled=True),
        meter=BrokenMeter(),
    )
    backend.record_counter("uag.test", 1)
    backend.record_histogram("uag.test", 1)

from __future__ import annotations

from contextlib import contextmanager

from uagent.runtime.observability.semantic_mapping import map_span
from uagent.runtime.round_contracts import (
    ContextPlan,
    ProviderProjection,
    ProviderRuntimeRegistry,
    RoundIdentifiers,
    SerializedRequest,
    StreamEvent,
)
from uagent.runtime.round_orchestrator import RoundOrchestrator


class _Span:
    def set_attribute(self, key, value) -> None:
        return None

    def add_event(self, name, attributes=None) -> None:
        return None

    def record_exception(self, exc) -> None:
        return None

    def set_status(self, status, description=None) -> None:
        return None


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.mapped = None

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        self.mapped = map_span(operation, attributes)
        yield _Span()

    def record_event(self, name, attributes=None):
        return None

    def current_trace_ids(self):
        return None


class _Runtime:
    def project(self, plan, session):
        return ProviderProjection(
            plan.plan_id,
            "projection",
            "fake",
            "resolved-model",
            "chat",
            plan.messages,
        )

    def serialize(self, projection):
        return SerializedRequest(
            RoundIdentifiers("turn", "round", "attempt", "request", "stream", 0),
            projection.plan_id,
            projection.projection_id,
            "fake",
            "resolved-model",
            {},
        )

    def run(self, request, cancellation):
        yield StreamEvent(
            "ResponseStarted", request.identifiers, 0, 0.0, {"stream_mode": "delta"}
        )
        yield StreamEvent(
            "ResponseCompleted", request.identifiers, 1, 0.0, {"response_id": "resp"}
        )


class _Cancellation:
    def is_cancelled(self):
        return False


def test_chat_span_is_mapped_after_model_is_resolved(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: backend,
    )
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _Runtime())

    RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={},
        cancellation=_Cancellation(),
    )

    assert backend.mapped is not None
    assert backend.mapped.name == "chat resolved-model"
    assert backend.mapped.attributes["gen_ai.request.model"] == "resolved-model"
    assert backend.mapped.attributes["gen_ai.provider.name"] == "fake"

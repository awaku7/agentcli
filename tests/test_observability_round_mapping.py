from __future__ import annotations

from contextlib import contextmanager

import pytest

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
    def __init__(self) -> None:
        self.attributes = {}
        self.exceptions = []
        self.status = []

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def add_event(self, name, attributes=None) -> None:
        return None

    def record_exception(self, exc) -> None:
        self.exceptions.append(type(exc).__name__)

    def set_status(self, status, description=None) -> None:
        self.status.append((status, description))


class _Backend:
    enabled = True

    def __init__(self) -> None:
        self.mapped = None
        self.span = _Span()

    @contextmanager
    def start_span(self, operation, *, attributes=None, root=False):
        self.mapped = map_span(operation, attributes)
        yield self.span

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


class _ProjectionFailureRuntime:
    def project(self, plan, session):
        raise ValueError("projection failed")


class _Cancellation:
    def is_cancelled(self):
        return False


def _registry() -> ProviderRuntimeRegistry:
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _Runtime())
    return registry


def test_chat_span_is_mapped_after_model_is_resolved(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: backend,
    )

    RoundOrchestrator(_registry()).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={},
        cancellation=_Cancellation(),
    )

    assert backend.mapped is not None
    assert backend.mapped.name == "chat resolved-model"
    assert backend.mapped.attributes["gen_ai.request.model"] == "resolved-model"
    assert backend.mapped.attributes["gen_ai.provider.name"] == "fake"
    assert backend.span.status[-1] == ("ok", None)


def test_chat_span_is_not_marked_ok_before_response_sync_succeeds(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: backend,
    )

    class FailingResponsesRuntime:
        def sync_completed_response(self, response_id, *, tool_calls):
            raise RuntimeError("duplicate tool call id")

    with pytest.raises(RuntimeError, match="duplicate tool call id"):
        RoundOrchestrator(_registry()).run(
            ContextPlan("plan", ({"role": "user", "content": "hi"},)),
            provider="fake",
            session={"responses_runtime": FailingResponsesRuntime()},
            cancellation=_Cancellation(),
        )

    assert ("ok", None) not in backend.span.status


def test_projection_failure_emits_error_chat_span(monkeypatch) -> None:
    backend = _Backend()
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: backend,
    )
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _ProjectionFailureRuntime())

    with pytest.raises(ValueError, match="projection failed"):
        RoundOrchestrator(registry).run(
            ContextPlan("plan", ({"role": "user", "content": "hi"},)),
            provider="fake",
            session={},
            cancellation=_Cancellation(),
        )

    assert backend.mapped is not None
    assert backend.mapped.name == "chat"
    assert backend.mapped.attributes["gen_ai.provider.name"] == "fake"
    assert backend.mapped.attributes["uag.llm.phase"] == "prepare"
    assert backend.span.attributes["uag.status"] == "failed"
    assert backend.span.exceptions == ["ValueError"]
    assert backend.span.status[-1] == ("error", "ValueError")

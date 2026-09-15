from dataclasses import dataclass

from uagent.runtime.round_contracts import (
    ContextPlan,
    ProviderProjection,
    ProviderRuntimeRegistry,
    RoundIdentifiers,
    SerializedRequest,
    StreamEvent,
)
from uagent.runtime.round_orchestrator import RoundOrchestrator


@dataclass
class _Runtime:
    def project(self, plan, session):
        return ProviderProjection(
            plan.plan_id, "projection", "fake", "model", "chat", plan.messages
        )

    def serialize(self, projection):
        return SerializedRequest(
            RoundIdentifiers("turn", "round", "attempt", "request", "stream", 0),
            projection.plan_id,
            projection.projection_id,
            "fake",
            "model",
            {},
        )

    def run(self, request, cancellation):
        yield StreamEvent(
            "ResponseStarted", request.identifiers, 0, 0.0, {"stream_mode": "delta"}
        )
        yield StreamEvent("TextDelta", request.identifiers, 1, 0.0, {"text": "hello"})
        yield StreamEvent("ResponseCompleted", request.identifiers, 2, 0.0, {})


class _Cancellation:
    def is_cancelled(self):
        return False


def test_orchestrator_runs_three_stage_contract() -> None:
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _Runtime())

    round_ = RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={},
        cancellation=_Cancellation(),
    )

    assert round_.result.status == "completed"
    assert round_.result.assistant_text == "hello"
    assert [event.type for event in round_.events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]

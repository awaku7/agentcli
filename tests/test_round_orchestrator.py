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
        yield StreamEvent(
            "ResponseCompleted",
            request.identifiers,
            2,
            0.0,
            {"response_id": "resp_1"},
        )


class _ResponsesRuntime:
    def __init__(self) -> None:
        self.calls = []

    def sync_completed_response(self, response_id, *, tool_calls=()):
        self.calls.append((response_id, tuple(tool_calls)))


class _Cancellation:
    def is_cancelled(self):
        return False


class _TerminalRuntime(_Runtime):
    def __init__(self, terminal_type: str) -> None:
        self.terminal_type = terminal_type

    def run(self, request, cancellation):
        yield StreamEvent(
            "ResponseStarted", request.identifiers, 0, 0.0, {"stream_mode": "delta"}
        )
        yield StreamEvent(self.terminal_type, request.identifiers, 1, 0.0, {})


class _TerminalResponsesRuntime:
    def __init__(self) -> None:
        self.transitions = []

    def cancel(self):
        self.transitions.append("cancel")

    def timeout(self):
        self.transitions.append("timeout")

    def interrupt(self):
        self.transitions.append("interrupt")

    def fail(self):
        self.transitions.append("fail")


def test_orchestrator_runs_three_stage_contract() -> None:
    registry = ProviderRuntimeRegistry()
    responses_runtime = _ResponsesRuntime()
    registry.register("fake", _Runtime())

    round_ = RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={
            "responses_runtime": responses_runtime,
            "recovery_hint": {"strategy": "bounded_rollback"},
        },
        cancellation=_Cancellation(),
    )

    assert round_.result.status == "completed"
    assert round_.result.assistant_text == "hello"
    assert round_.result.continuation_update == {"response_id": "resp_1"}
    assert round_.result.recovery_hint == {"strategy": "bounded_rollback"}
    assert responses_runtime.calls == [("resp_1", ())]
    assert [event.type for event in round_.events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]


def test_orchestrator_synchronizes_non_successful_response_terminals() -> None:
    transitions = {
        "ResponseCancelled": "cancel",
        "ResponseTimedOut": "timeout",
        "ResponseInterrupted": "interrupt",
        "ResponseFailed": "fail",
    }
    for event_type, expected in transitions.items():
        registry = ProviderRuntimeRegistry()
        responses_runtime = _TerminalResponsesRuntime()
        registry.register("fake", _TerminalRuntime(event_type))

        result = (
            RoundOrchestrator(registry)
            .run(
                ContextPlan("plan", ({"role": "user", "content": "hi"},)),
                provider="fake",
                session={"responses_runtime": responses_runtime},
                cancellation=_Cancellation(),
            )
            .result
        )

        assert result.status != "completed"
        assert responses_runtime.transitions == [expected]

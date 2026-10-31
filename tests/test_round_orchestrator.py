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
    observed_events = []

    round_ = RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={
            "responses_runtime": responses_runtime,
            "recovery_hint": {"strategy": "bounded_rollback"},
        },
        cancellation=_Cancellation(),
        on_event=observed_events.append,
    )

    assert round_.result.status == "completed"
    assert round_.result.assistant_text == "hello"
    assert round_.result.continuation_update == {"response_id": "resp_1"}
    assert round_.result.recovery_hint == {"strategy": "bounded_rollback"}
    assert round_.result.summary is not None
    assert round_.result.summary.to_dict()["status"] == "completed"
    assert round_.result.summary.to_dict()["event_count"] == 3
    assert responses_runtime.calls == [("resp_1", ())]
    assert [event.type for event in round_.events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert [event.type for event in observed_events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]


def test_orchestrator_progress_observer_errors_do_not_fail_round() -> None:
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _Runtime())

    def broken_observer(_event) -> None:
        raise RuntimeError("display failed")

    result = RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={},
        cancellation=_Cancellation(),
        on_event=broken_observer,
    )

    assert result.result.status == "completed"


def test_orchestrator_emits_projection_and_request_telemetry(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.log_event",
        lambda event_code, **fields: captured.update(
            {"event_code": event_code, **fields}
        ),
    )
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _Runtime())

    RoundOrchestrator(registry).run(
        ContextPlan(
            "plan",
            ({"role": "user", "content": "hi"},),
            telemetry={"fallback_count": 2},
        ),
        provider="fake",
        session={
            "recovery_hint": {"strategy": "bounded_rollback"},
            "usage_before": {"input_tokens": 10, "output_tokens": 2},
            "usage_after": {"input_tokens": 15, "output_tokens": 5},
        },
        cancellation=_Cancellation(),
    )

    assert captured["event_code"] == "llm.round.completed"
    assert captured["request_tokens"] > 0
    assert captured["projection_size"] > 0
    assert captured["tool_schema_size"] >= 0
    assert captured["recovery_strategy"] == "bounded_rollback"
    assert captured["fallback_count"] == 2
    assert captured["duplicate_event_count"] == 0
    assert captured["out_of_order_event_count"] == 0
    assert captured["input_tokens_delta"] == 5
    assert captured["output_tokens_delta"] == 3
    assert captured["status"] == "completed"
    assert captured["event_count"] == 3
    assert captured["usage_delta"] == {
        "input_tokens_delta": 5,
        "output_tokens_delta": 3,
    }


def test_orchestrator_exposes_bounded_round_summary() -> None:
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _Runtime())

    result = (
        RoundOrchestrator(registry)
        .run(
            ContextPlan("plan", ({"role": "user", "content": "hi"},)),
            provider="fake",
            session={},
            cancellation=_Cancellation(),
        )
        .result
    )

    assert result.summary is not None
    summary = result.summary.to_dict()
    assert summary["assistant_chars"] == len("hello")
    assert summary["tool_call_count"] == 0
    assert summary["usage_delta"] == {}
    assert "content" not in summary


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


class _MeasuredUsageRuntime(_Runtime):
    def run(self, request, cancellation):
        yield StreamEvent(
            "ResponseStarted", request.identifiers, 0, 0.0, {"stream_mode": "delta"}
        )
        yield StreamEvent(
            "ResponseCompleted",
            request.identifiers,
            1,
            0.0,
            {
                "response_id": "resp_usage",
                "usage": {"input_tokens": 14, "output_tokens": 6},
            },
        )


def test_orchestrator_uses_provider_response_usage_without_prior_subtraction() -> None:
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _MeasuredUsageRuntime())
    result = RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={
            "usage_before": {"input_tokens": 100, "output_tokens": 50},
            "usage_after": {"input_tokens": 110, "output_tokens": 55},
        },
        cancellation=_Cancellation(),
    )
    assert result.result.summary is not None
    assert result.result.summary.usage_delta == {
        "input_tokens_delta": 14,
        "output_tokens_delta": 6,
    }


def test_orchestrator_keeps_estimates_distinct_from_reported_usage(monkeypatch):
    from contextlib import contextmanager

    class Span:
        def __init__(self):
            self.attributes = {}

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def add_event(self, name, attributes=None):
            pass

        def set_status(self, status, description=None):
            pass

    class Backend:
        @contextmanager
        def start_span(self, operation, *, attributes=None, root=False):
            yield span

    span = Span()
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: Backend(),
    )
    registry = ProviderRuntimeRegistry()
    registry.register("fake", _Runtime())
    RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={},
        cancellation=_Cancellation(),
    )
    assert span.attributes["uag.tokens.estimate.input"] > 0
    assert span.attributes["uag.tokens.estimate.output"] > 0
    assert "uag.tokens.reported.input" not in span.attributes
    assert "uag.tokens.reported.output" not in span.attributes


def test_orchestrator_estimates_tool_arguments_only_once(monkeypatch):
    from contextlib import contextmanager

    class Span:
        def __init__(self):
            self.attributes = {}

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def add_event(self, name, attributes=None):
            pass

        def set_status(self, status, description=None):
            pass

    class Backend:
        @contextmanager
        def start_span(self, operation, *, attributes=None, root=False):
            yield span

    class ToolRuntime(_Runtime):
        def run(self, request, cancellation):
            yield StreamEvent(
                "ResponseStarted", request.identifiers, 0, 0.0, {"stream_mode": "delta"}
            )
            yield StreamEvent(
                "ToolCallDelta",
                request.identifiers,
                1,
                0.0,
                {
                    "tool_call_id": "call_1",
                    "index": 0,
                    "name_fragment": "search",
                    "arguments_fragment": '{"q":"abc"}',
                },
            )
            yield StreamEvent(
                "ToolCallCompleted",
                request.identifiers,
                2,
                0.0,
                {
                    "name": "search",
                    "arguments": '{"q":"abc"}',
                    "validated_arguments": {"q": "abc"},
                    "tool_call_id": "call_1",
                    "index": 0,
                },
            )
            yield StreamEvent("ResponseCompleted", request.identifiers, 3, 0.0, {})

    span = Span()
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.get_observability_backend",
        lambda: Backend(),
    )
    monkeypatch.setattr(
        "uagent.runtime.round_orchestrator.estimate_tokens",
        lambda value, **kwargs: len(str(value)),
    )
    registry = ProviderRuntimeRegistry()
    registry.register("fake", ToolRuntime())
    RoundOrchestrator(registry).run(
        ContextPlan("plan", ({"role": "user", "content": "hi"},)),
        provider="fake",
        session={},
        cancellation=_Cancellation(),
    )
    assert span.attributes["uag.tokens.estimate.output"] == len('search{"q":"abc"}')

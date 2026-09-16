"""Provider-neutral orchestration of the three-stage LLM round contract."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping

from .round_contracts import (
    CancellationToken,
    ContextPlan,
    ProviderRuntimeRegistry,
    RoundResult,
    SerializedRequest,
    StreamEvent,
)
from .round_runtime import StreamEventValidator
from .stream_renderer import CollectingStreamRenderer
from .logging_setup import log_event


@dataclass(frozen=True)
class OrchestratedRound:
    request: SerializedRequest
    events: tuple[StreamEvent, ...]
    result: RoundResult


class RoundOrchestrator:
    """Execute ``ContextPlan → Projection → Request → StreamEvent`` once.

    It owns no provider SDK calls. Those remain behind the registered runtime,
    so the existing LLM loop can adopt this class behind a feature flag.
    """

    def __init__(self, registry: ProviderRuntimeRegistry) -> None:
        self._registry = registry

    def run(
        self,
        plan: ContextPlan,
        *,
        provider: str,
        session: Mapping[str, Any],
        cancellation: CancellationToken,
    ) -> OrchestratedRound:
        runtime = self._registry.resolve(provider)
        started = time.perf_counter()
        projection = runtime.project(plan, session)
        request = runtime.serialize(projection)
        validator = StreamEventValidator()
        events: list[StreamEvent] = []
        renderer = CollectingStreamRenderer()
        terminal: StreamEvent | None = None
        for event in runtime.run(request, cancellation):
            validator.accept(event)
            events.append(event)
            renderer.on_event(event)
            if event.type.startswith("Response") and event.type != "ResponseStarted":
                terminal = event
        validator.require_terminal()
        assert terminal is not None
        rendered = renderer.result()
        status_by_event = {
            "ResponseCompleted": "completed",
            "ResponseFailed": "failed",
            "ResponseCancelled": "cancelled",
            "ResponseTimedOut": "timed_out",
            "ResponseInterrupted": "interrupted",
        }
        status = status_by_event[terminal.type]
        continuation_update = {}
        if terminal.type == "ResponseCompleted":
            response_id = terminal.data.get("response_id")
            if response_id:
                continuation_update["response_id"] = str(response_id)
        result = RoundResult(
            identifiers=request.identifiers,
            plan_id=plan.plan_id,
            projection_id=projection.projection_id,
            status=status,  # type: ignore[arg-type]
            assistant_text=rendered.assistant_text,
            partial_text=rendered.partial_text,
            reasoning_text=rendered.reasoning_text,
            tool_calls=rendered.tool_calls,
            continuation_update=continuation_update,
            error=dict(terminal.data) if status == "failed" else None,
            recovery_hint=dict(session.get("recovery_hint") or {}),
        )
        log_event(
            "llm.round.completed",
            provider=request.provider,
            model=request.model,
            status=status,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            event_count=len(events),
            tool_call_count=len(rendered.tool_calls),
            assistant_chars=len(rendered.assistant_text),
            reasoning_chars=len(rendered.reasoning_text),
        )
        if continuation_update:
            responses_runtime = session.get("responses_runtime")
            sync_completed = getattr(responses_runtime, "sync_completed_response", None)
            if callable(sync_completed):
                sync_completed(
                    continuation_update["response_id"],
                    tool_calls=list(rendered.tool_calls),
                )
        else:
            responses_runtime = session.get("responses_runtime")
            terminal_transition = {
                "cancelled": "cancel",
                "timed_out": "timeout",
                "interrupted": "interrupt",
                "failed": "fail",
            }.get(status)
            if terminal_transition is not None:
                transition = getattr(responses_runtime, terminal_transition, None)
                if callable(transition):
                    transition()
        return OrchestratedRound(
            request=request,
            events=tuple(events),
            result=result,
        )

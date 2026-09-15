"""Provider-neutral orchestration of the three-stage LLM round contract."""

from __future__ import annotations

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
        projection = runtime.project(plan, session)
        request = runtime.serialize(projection)
        validator = StreamEventValidator()
        events: list[StreamEvent] = []
        text_parts: list[str] = []
        snapshot = ""
        reasoning_parts: list[str] = []
        tool_calls: list[Mapping[str, Any]] = []
        terminal: StreamEvent | None = None
        for event in runtime.run(request, cancellation):
            validator.accept(event)
            events.append(event)
            if event.type == "TextDelta":
                text_parts.append(str(event.data.get("text") or ""))
            elif event.type == "TextSnapshot":
                snapshot = str(event.data.get("text") or "")
            elif event.type == "ReasoningDelta":
                reasoning_parts.append(str(event.data.get("text") or ""))
            elif event.type == "ToolCallCompleted":
                tool_calls.append(dict(event.data))
            if event.type.startswith("Response") and event.type != "ResponseStarted":
                terminal = event
        validator.require_terminal()
        assert terminal is not None
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
            assistant_text=snapshot or "".join(text_parts),
            partial_text="".join(text_parts),
            reasoning_text="".join(reasoning_parts),
            tool_calls=tuple(tool_calls),
            continuation_update=continuation_update,
            error=dict(terminal.data) if status == "failed" else None,
        )
        if continuation_update:
            responses_runtime = session.get("responses_runtime")
            sync_completed = getattr(responses_runtime, "sync_completed_response", None)
            if callable(sync_completed):
                sync_completed(
                    continuation_update["response_id"],
                    tool_calls=tool_calls,
                )
        return OrchestratedRound(
            request=request,
            events=tuple(events),
            result=result,
        )

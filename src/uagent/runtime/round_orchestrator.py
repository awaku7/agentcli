"""Provider-neutral orchestration of the three-stage LLM round contract."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

from .context_tokens import estimate_tokens
from .telemetry import reconcile_usage

from .round_contracts import (
    CancellationToken,
    ContextPlan,
    ProviderRuntimeRegistry,
    RoundResult,
    RoundSummary,
    SerializedRequest,
    StreamEvent,
)
from .round_runtime import StreamEventValidator
from .stream_renderer import CollectingStreamRenderer
from .logging_setup import log_event
from .observability.api import ObservabilitySpan
from .observability.bootstrap import get_observability_backend


def _json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    except Exception:
        return len(str(value or ""))


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
        backend = get_observability_backend()
        with backend.start_span(
            "chat",
            attributes={
                "uag.llm.provider": request.provider,
                "uag.llm.model": request.model,
            },
        ) as observability_span:
            return self._run_observed(
                plan,
                runtime=runtime,
                projection=projection,
                request=request,
                session=session,
                cancellation=cancellation,
                observability_span=observability_span,
                started=started,
            )

    def _run_observed(
        self,
        plan: ContextPlan,
        *,
        runtime: Any,
        projection: Any,
        request: SerializedRequest,
        session: Mapping[str, Any],
        cancellation: CancellationToken,
        observability_span: ObservabilitySpan,
        started: float,
    ) -> OrchestratedRound:
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
        recovery_hint = dict(session.get("recovery_hint") or {})
        plan_telemetry = dict(plan.telemetry or {})
        request_input = request.payload.get(
            "input", request.payload.get("messages", projection.messages)
        )
        request_tokens = estimate_tokens(
            request_input,
            provider=request.provider,
            model=request.model,
        )
        projection_size = _json_size(
            {
                "messages": projection.messages,
                "tool_specs": projection.tool_specs,
                "options": projection.options,
            }
        )
        tool_schema_size = _json_size(
            request.payload.get("tools", projection.tool_specs)
        )
        usage_after = session.get("usage_after")
        if not isinstance(usage_after, Mapping):
            usage_after = terminal.data.get("usage")
        usage_delta = reconcile_usage(
            session.get("usage_before"),
            usage_after if isinstance(usage_after, Mapping) else None,
        )
        summary = RoundSummary(
            status=status,  # type: ignore[arg-type]
            duration_ms=(time.perf_counter() - started) * 1000.0,
            event_count=len(events),
            tool_call_count=len(rendered.tool_calls),
            assistant_chars=len(rendered.assistant_text),
            reasoning_chars=len(rendered.reasoning_text),
            request_tokens=request_tokens,
            tool_schema_size=tool_schema_size,
            projection_size=projection_size,
            recovery_strategy=str(recovery_hint.get("strategy", "")),
            fallback_count=int(plan_telemetry.get("fallback_count", 0) or 0),
            duplicate_event_count=validator.duplicate_events,
            out_of_order_event_count=validator.out_of_order_events,
            usage_delta=usage_delta,
        )
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
            recovery_hint=recovery_hint,
            summary=summary,
        )
        observability_span.set_attribute("uag.status", status)
        observability_span.set_attribute("uag.duration_ms", summary.duration_ms)
        observability_span.set_attribute(
            "uag.tokens.estimate.input", summary.request_tokens
        )
        reported_names = {
            "input_tokens_delta": "uag.tokens.reported.input",
            "output_tokens_delta": "uag.tokens.reported.output",
            "total_tokens_delta": "uag.tokens.reported.total",
        }
        for key, attribute_name in reported_names.items():
            if key in usage_delta:
                observability_span.set_attribute(attribute_name, usage_delta[key])
        if status == "completed":
            observability_span.set_status("ok")
        elif status in {"failed", "timed_out", "interrupted"}:
            error_type = str((result.error or {}).get("error_type") or status)
            observability_span.set_status("error", error_type)
        observability_span.add_event(
            "llm.round.completed",
            {
                "uag.status": status,
                "uag.tool_call_count": summary.tool_call_count,
            },
        )
        log_event(
            "llm.round.completed",
            provider=request.provider,
            model=request.model,
            **summary.to_dict(),
            **usage_delta,
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

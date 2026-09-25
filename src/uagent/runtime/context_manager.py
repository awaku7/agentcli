"""Unified facade for UAG context-management subsystems."""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from .active_context import (
    ActiveContext,
    ActiveContextBuilder,
    ContextCandidate,
    ContextDecision,
)
from .context_budget import ContextBudget
from .context_decision import ContextDecisionEngine
from .context_retrieval import retrieve_candidates
from .context_plan_builder import build_context_plan as _build_context_plan
from .context_policy import ContextPolicy
from .context_tools import ToolDefinitionSelection, select_tool_definitions
from .observability.bootstrap import get_observability_backend
from .round_contracts import ContextPlan
from .round_identity import WorkspaceKeyProvider
from .tool_result_manager import (
    ContextResultManager,
    ToolResultProjections,
    ToolResultRecord,
)


def _record_context_observability(
    backend: Any,
    span: Any,
    active: ActiveContext,
    *,
    kind: str,
    input_count: int,
) -> None:
    """Record aggregate-only Context telemetry; never affect runtime behavior."""

    try:
        report = active.report
        span.set_attribute("uag.context.kind", kind)
        span.set_attribute("uag.context.input_count", max(0, int(input_count)))
        span.set_attribute("uag.context.raw_chars", report.raw_chars)
        span.set_attribute("uag.context.active_chars", report.active_chars)
        span.set_attribute("uag.context.saved_chars", report.saved_chars)
        if report.raw_tokens is not None:
            span.set_attribute("uag.context.raw_tokens", report.raw_tokens)
        if report.active_tokens is not None:
            span.set_attribute("uag.context.active_tokens", report.active_tokens)
        if report.saved_tokens is not None:
            span.set_attribute("uag.context.saved_tokens", report.saved_tokens)
        if report.saved_ratio is not None:
            span.set_attribute("uag.context.saved_ratio", report.saved_ratio)

        metric_attributes = {"uag.context.kind": kind}
        backend.record_histogram(
            "uag.context.raw.chars", report.raw_chars, metric_attributes
        )
        backend.record_histogram(
            "uag.context.active.chars", report.active_chars, metric_attributes
        )
        backend.record_histogram(
            "uag.context.saved.chars", report.saved_chars, metric_attributes
        )
        if report.raw_tokens is not None:
            backend.record_histogram(
                "uag.context.raw.tokens", report.raw_tokens, metric_attributes
            )
        if report.active_tokens is not None:
            backend.record_histogram(
                "uag.context.active.tokens", report.active_tokens, metric_attributes
            )
        if report.saved_tokens is not None:
            backend.record_histogram(
                "uag.context.saved.tokens", report.saved_tokens, metric_attributes
            )
        if report.saved_ratio is not None:
            backend.record_histogram(
                "uag.context.saved.ratio", report.saved_ratio, metric_attributes
            )

        action_counts = Counter(decision.action for decision in active.decisions)
        for action, count in action_counts.items():
            normalized = str(action or "").upper()
            span.set_attribute(
                f"uag.context.decisions.{normalized.casefold()}", int(count)
            )
            backend.record_counter(
                "uag.context.decisions",
                int(count),
                {"uag.context.decision.action": normalized},
            )
        span.set_status("ok")
    except Exception:
        pass


class ContextManager:
    """Coordinate policy, budgets, Tool Results, and bounded retrieval."""

    def __init__(
        self,
        *,
        policy: ContextPolicy | None = None,
        budget: ContextBudget | None = None,
        result_manager: ContextResultManager | None = None,
    ) -> None:
        self.policy = policy or ContextPolicy.from_environment()
        self.budget = budget or (
            ContextBudget.without_limit()
            if (
                not self.policy.budget_enabled
                or (
                    self.policy.budget_unlimited
                    and self.policy.budget_chars == ContextPolicy().budget_chars
                    and self.policy.budget_tokens is None
                )
            )
            else ContextBudget(
                total_chars=self.policy.budget_chars,
                total_tokens=self.policy.budget_tokens,
            )
        )
        self.results = result_manager or ContextResultManager(
            max_preview_rows=self.policy.tool_result_max_rows
        )
        self.active_context_builder = ActiveContextBuilder(
            budget=self.budget,
            provider=self.policy.provider,
            model=self.policy.model,
        )
        self.decision_engine = ContextDecisionEngine()
        self.last_active_context: ActiveContext | None = None

    @classmethod
    def from_environment(
        cls, *, provider: str = "", model: str = ""
    ) -> "ContextManager":
        return cls(
            policy=ContextPolicy.from_environment(provider=provider, model=model)
        )

    def process_result(
        self, value: Any, **kwargs: Any
    ) -> tuple[ToolResultRecord, ToolResultProjections]:
        """Classify and project a Tool Result through the shared manager."""
        return self.results.process(value, **kwargs)

    def retrieve_context(
        self,
        records: list[dict[str, Any]],
        *,
        max_chars: int = 8_000,
    ) -> str:
        """Format retrieved records for bounded LLM injection."""
        return self.results.format_retrieved_context(records, max_chars=max_chars)

    def retrieve_candidates(
        self,
        records: Sequence[dict[str, Any]],
        *,
        query: str = "",
        max_candidates: int = 20,
    ) -> list[ContextCandidate]:
        """Retrieve ranked provider-neutral candidates from persisted records."""
        return retrieve_candidates(records, query=query, max_candidates=max_candidates)

    def usage(self, **sections: int) -> dict[str, Any]:
        return self.budget.usage(**sections)

    def build_context_plan(
        self,
        *,
        workspace_id: str,
        messages: Sequence[dict[str, Any]],
        tool_specs: Sequence[dict[str, Any]] = (),
        decisions: Sequence[dict[str, Any]] = (),
        telemetry: dict[str, Any] | None = None,
        key_provider: WorkspaceKeyProvider | None = None,
        history_revision: str = "",
        schema_revision: str = "1",
        provider: str | None = None,
        model: str | None = None,
    ) -> ContextPlan:
        """Create the immutable round hand-off owned by this manager.

        Context selection and policy metadata are completed before the
        provider boundary. Callers should use this method so every round
        receives the same ``ContextPlan`` construction path.
        """
        policy = {
            "provider": provider if provider is not None else self.policy.provider,
            "model": model if model is not None else self.policy.model,
            "budget_enabled": self.policy.budget_enabled,
            "budget_chars": self.policy.budget_chars,
            "budget_unlimited": self.policy.budget_unlimited,
            "budget_tokens": self.policy.budget_tokens,
        }
        return _build_context_plan(
            workspace_id=workspace_id,
            messages=messages,
            tool_specs=tool_specs,
            decisions=decisions,
            policy=policy,
            telemetry=telemetry or {},
            key_provider=key_provider,
            history_revision=history_revision,
            schema_revision=schema_revision,
        )

    def build_message_context(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        """Build a provider-neutral context while preserving message order."""
        backend = get_observability_backend()
        with backend.start_span(
            "uag.context.build",
            attributes={
                "uag.context.kind": "messages",
                "uag.context.input_count": len(messages),
            },
        ) as span:
            active = self.active_context_builder.build_message_context(
                messages, budget=budget or self.budget
            )
            _record_context_observability(
                backend,
                span,
                active,
                kind="messages",
                input_count=len(messages),
            )
        self.last_active_context = active
        return active

    def optimize_tool_definitions(
        self,
        tool_specs: Sequence[dict[str, Any]] | None,
        *,
        task: str = "",
        max_tools: int | None = None,
        budget: ContextBudget | None = None,
    ) -> ToolDefinitionSelection:
        """Select whole, relevant tool schemas within the context budget."""
        return select_tool_definitions(
            tool_specs,
            task=task,
            budget=budget or self.budget,
            provider=self.policy.provider,
            model=self.policy.model,
            max_tools=max_tools,
        )

    def build_active_context(
        self,
        *,
        task: str,
        candidates: Sequence[ContextCandidate],
        decisions: Sequence[ContextDecision] | None = None,
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        """Run decisions and build the provider-neutral context for one call."""
        backend = get_observability_backend()
        with backend.start_span(
            "uag.context.build",
            attributes={
                "uag.context.kind": "candidates",
                "uag.context.input_count": len(candidates),
            },
        ) as span:
            active_budget = budget or self.budget
            selected = (
                list(decisions)
                if decisions is not None
                else self.decision_engine.decide(candidates, budget=active_budget)
            )
            active = self.active_context_builder.build_active_context(
                task=task,
                candidates=candidates,
                decisions=selected,
                budget=active_budget,
            )
            _record_context_observability(
                backend,
                span,
                active,
                kind="candidates",
                input_count=len(candidates),
            )
        self.last_active_context = active
        return active

    def debug_snapshot(self) -> dict[str, Any]:
        """Return the latest context telemetry and decision log."""
        if self.last_active_context is None:
            return {}
        return self.last_active_context.debug_snapshot()

    def build_active_context_from_records(
        self,
        *,
        task: str,
        records: Sequence[dict[str, Any]],
        query: str = "",
        max_candidates: int = 20,
        max_retrieval_rounds: int = 3,
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        """Run retrieval, scoring, decision, and projection as one pipeline.

        When the initial retrieval produces no usable context, bounded rounds
        of broader retrieval are attempted. This keeps ``RETRIEVE_MORE`` a
        bounded runtime behavior without making persistence responsible for
        active-context selection.
        """
        if max_candidates < 0:
            raise ValueError("max_candidates must be non-negative")
        if max_retrieval_rounds < 1:
            raise ValueError("max_retrieval_rounds must be positive")

        limit = max_candidates
        active: ActiveContext | None = None
        for _ in range(max_retrieval_rounds):
            candidates = self.retrieve_candidates(
                records, query=query or task, max_candidates=limit
            )
            active = self.build_active_context(
                task=task,
                candidates=candidates,
                budget=budget,
            )
            if not self.decision_engine.needs_additional_retrieval(active.decisions):
                return active
            unique_record_ids = {
                str(record.get("result_id") or record.get("item_id") or f"record-{i}")
                for i, record in enumerate(records)
            }
            if len(candidates) >= len(unique_record_ids):
                return active
            limit = max(1, limit * 2)

        assert active is not None
        return active

    def decide_context(
        self, candidates: Sequence[ContextCandidate]
    ) -> list[ContextDecision]:
        """Score and budget candidates before building the active context."""
        return self.decision_engine.decide(candidates, budget=self.budget)


__all__ = ["ContextManager"]

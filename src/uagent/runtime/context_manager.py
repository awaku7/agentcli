"""Unified facade for UAG context-management subsystems."""

from __future__ import annotations

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
from .context_policy import ContextPolicy
from .tool_result_manager import (
    ContextResultManager,
    ToolResultProjections,
    ToolResultRecord,
)


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
                )
            )
            else ContextBudget(total_chars=self.policy.budget_chars)
        )
        self.results = result_manager or ContextResultManager(
            max_preview_rows=self.policy.tool_result_max_rows
        )
        self.active_context_builder = ActiveContextBuilder(budget=self.budget)
        self.decision_engine = ContextDecisionEngine()

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

    def build_message_context(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        """Build a provider-neutral context while preserving message order."""
        return self.active_context_builder.build_message_context(
            messages, budget=budget or self.budget
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
        active_budget = budget or self.budget
        selected = (
            list(decisions)
            if decisions is not None
            else self.decision_engine.decide(candidates, budget=active_budget)
        )
        return self.active_context_builder.build_active_context(
            task=task,
            candidates=candidates,
            decisions=selected,
            budget=active_budget,
        )

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
            # Duplicate persisted IDs are removed by retrieval, so compare
            # against the number of unique records before requesting another
            # round. This keeps replayed tool results from causing pointless
            # retrieval rounds.
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

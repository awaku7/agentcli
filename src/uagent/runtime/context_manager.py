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
        self.budget = budget or ContextBudget(total_chars=self.policy.budget_chars)
        self.results = result_manager or ContextResultManager()
        self.active_context_builder = ActiveContextBuilder(budget=self.budget)

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

    def usage(self, **sections: int) -> dict[str, Any]:
        return self.budget.usage(**sections)

    def build_message_context(
        self, messages: Sequence[dict[str, Any]]
    ) -> ActiveContext:
        """Build a provider-neutral context while preserving message order."""
        return self.active_context_builder.build_message_context(
            messages, budget=self.budget
        )

    def build_active_context(
        self,
        *,
        task: str,
        candidates: Sequence[ContextCandidate],
        decisions: Sequence[ContextDecision],
    ) -> ActiveContext:
        """Build the provider-neutral context for one LLM call."""
        return self.active_context_builder.build_active_context(
            task=task,
            candidates=candidates,
            decisions=decisions,
        )


__all__ = ["ContextManager"]

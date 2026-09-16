"""Retry authorization boundary for one legacy LLM round."""

from __future__ import annotations

from .round_runtime import RoundAttemptBudget, RetryRequest


class RoundRetryCoordinator:
    """Own the shared attempt budget and reason-specific retry checks."""

    def __init__(self, max_retries_429: int) -> None:
        self.budget = RoundAttemptBudget(
            total_limit=max(1, max_retries_429 + 4),
            reason_limits={
                "stale_continuation": 1,
                "feature_fallback": 2,
                "transport": max(1, max_retries_429 + 1),
                "client_recreate": 1,
            },
        )

    def authorize(self, reason: str, detail: str) -> bool:
        return self.budget.try_consume(RetryRequest(reason, detail))


__all__ = ["RoundRetryCoordinator"]

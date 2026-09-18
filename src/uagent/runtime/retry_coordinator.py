"""Retry authorization boundary for one legacy LLM round."""

from __future__ import annotations

from typing import Any, Callable

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

    def rate_limit_step(
        self,
        *,
        exception: Exception,
        provider: str,
        model: str,
        attempt: int,
        max_retries: int,
        base: float,
        cap: float,
        recreate_client_fn: Callable[[], Any],
    ) -> tuple[int, Any | None, str]:
        """Run rate-limit backoff and charge the shared transport budget."""
        from ..llm_errors import _rate_limit_retry_step

        next_attempt, new_client, action = _rate_limit_retry_step(
            exception=exception,
            provider=provider,
            model=model,
            attempt=attempt,
            max_retries=max_retries,
            base=base,
            cap=cap,
            recreate_client_fn=recreate_client_fn,
        )
        if action == "retry":
            authorized = self.authorize(
                "transport", f"{provider}:{model}:{type(exception).__name__}"
            )
            if not authorized:
                return next_attempt, None, "give_up"
            from .logging_setup import log_event

            log_event(
                "llm.retry.authorized",
                provider=provider,
                model=model,
                retry_reason="transport",
                retry_attempt=next_attempt,
                additional_request_count=1,
                additional_token_count=None,
            )
        return next_attempt, new_client, action


__all__ = ["RoundRetryCoordinator"]

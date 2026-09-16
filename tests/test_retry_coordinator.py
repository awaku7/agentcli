from __future__ import annotations

from uagent.runtime.retry_coordinator import RoundRetryCoordinator


def test_retry_coordinator_applies_reason_limits() -> None:
    coordinator = RoundRetryCoordinator(max_retries_429=0)

    assert coordinator.authorize("stale_continuation", "first") is True
    assert coordinator.authorize("stale_continuation", "second") is False
    assert coordinator.authorize("feature_fallback", "first") is True
    assert coordinator.authorize("feature_fallback", "second") is True
    assert coordinator.authorize("feature_fallback", "third") is False


__all__ = []

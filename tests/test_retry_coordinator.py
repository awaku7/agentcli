from __future__ import annotations

from uagent.runtime.retry_coordinator import RoundRetryCoordinator


def test_rate_limit_step_charges_shared_transport_budget(monkeypatch) -> None:
    calls = []

    def fake_rate_limit_step(**kwargs):
        calls.append(kwargs)
        return kwargs["attempt"] + 1, None, "retry"

    monkeypatch.setattr("uagent.llm_errors._rate_limit_retry_step", fake_rate_limit_step)
    coordinator = RoundRetryCoordinator(max_retries_429=0)
    kwargs = {
        "exception": RuntimeError("429"),
        "provider": "openai",
        "model": "gpt-test",
        "max_retries": 0,
        "base": 0.0,
        "cap": 0.0,
        "recreate_client_fn": lambda: None,
    }

    assert coordinator.rate_limit_step(attempt=0, **kwargs)[2] == "retry"
    assert coordinator.rate_limit_step(attempt=1, **kwargs)[2] == "give_up"
    assert len(calls) == 2


def test_retry_coordinator_applies_reason_limits() -> None:
    coordinator = RoundRetryCoordinator(max_retries_429=0)

    assert coordinator.authorize("stale_continuation", "first") is True
    assert coordinator.authorize("stale_continuation", "second") is False
    assert coordinator.authorize("feature_fallback", "first") is True
    assert coordinator.authorize("feature_fallback", "second") is True
    assert coordinator.authorize("feature_fallback", "third") is False


__all__ = []

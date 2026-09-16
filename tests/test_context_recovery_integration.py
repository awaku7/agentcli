"""Regression contracts for context-overflow recovery boundaries.

These tests deliberately exercise the provider-neutral recovery seam without
entering the LLM loop.  The loop may choose legacy fallback when a remote
mutation is stale or fails; the recovery contracts must make that decision
safe and observable.
"""

from __future__ import annotations

from dataclasses import dataclass

from uagent.providers.responses_recovery_port import ResponsesRecoveryPort
from uagent.runtime.context_recovery import ContextRecoveryManager, RecoveryPlan
from uagent.runtime.round_contracts import ContextPlan
from uagent.runtime.round_runtime import RetryRequest, RoundAttemptBudget
from uagent.uagent_llm import _apply_remote_recovery_update


def _context_plan() -> ContextPlan:
    return ContextPlan(
        plan_id="plan-context-overflow",
        messages=(
            {"id": "first", "role": "system", "content": "stable"},
            {"id": "largest", "role": "user", "content": "x" * 2_000},
            {"id": "tail", "role": "assistant", "content": "retry me"},
        ),
    )


def test_local_overflow_recovery_is_replayable_and_does_not_mutate_history() -> None:
    context_plan = _context_plan()
    before = context_plan.messages
    manager = ContextRecoveryManager(lookback=3)

    first = manager.plan(
        context_plan=context_plan,
        projection_id="projection-1",
        error_text="input token count exceeds the maximum number of tokens allowed",
        attempt_id="attempt-1",
    )
    second = manager.plan(
        context_plan=context_plan,
        projection_id="projection-1",
        error_text="input token count exceeds the maximum number of tokens allowed",
        attempt_id="attempt-1",
    )
    recovered = manager.apply_local(first, context_plan)

    assert first.recovery_id == second.recovery_id
    assert first.strategy == "bounded_rollback"
    assert first.omitted_message_indexes == (1, 2)
    assert first.omitted_message_ids == ("largest", "tail")
    assert first.local_history_mutation is False
    assert first.projection_mutation is True
    assert context_plan.messages == before
    assert tuple(message["id"] for message in recovered.messages) == ("first",)
    assert recovered.omitted_message_indexes == (1, 2)

    selected = manager.select_bounded_rollback(list(context_plan.messages), lookback=3)
    assert selected[0] == 1
    assert selected[1] > 2_000
    assert selected[2] == 2
    projection = manager.bounded_rollback_projection(
        list(context_plan.messages), lookback=3
    )
    assert projection is not None
    projected_messages, metadata = projection
    assert tuple(message["id"] for message in projected_messages) == ("first",)
    assert metadata["removed"] == 2
    assert context_plan.messages == before


def test_context_overflow_consumes_the_single_shared_retry_budget() -> None:
    budget = RoundAttemptBudget(total_limit=1)
    overflow_retry = RetryRequest("context_overflow", "bounded rollback")

    assert budget.try_consume(overflow_retry) is True
    assert budget.try_consume(overflow_retry) is False
    assert (
        budget.try_consume(RetryRequest("transport", "must not double retry")) is False
    )
    assert budget.remaining == 0


@dataclass
class _Response:
    id: str


class _Manager:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def compact(self, response_id: str, *, input=None):
        self.calls.append(response_id)
        if self.fail:
            raise RuntimeError("remote unavailable")
        return _Response("compacted-response")


def _remote_plan(recovery_id: str) -> RecoveryPlan:
    return RecoveryPlan(
        recovery_id=recovery_id,
        plan_id="plan-context-overflow",
        projection_id="projection-1",
        classification="context_overflow",
        strategy="provider_compact",
        remote_session_mutation=True,
    )


def test_remote_stale_or_failure_preserves_legacy_fallback_preconditions() -> None:
    stale_manager = _Manager()
    stale = ResponsesRecoveryPort(stale_manager).apply(
        _remote_plan("recovery-stale"),
        {"response_id": "response-1", "session_generation": 3},
        expected_session_generation=2,
    )

    failing_manager = _Manager(fail=True)
    failed = ResponsesRecoveryPort(failing_manager).apply(
        _remote_plan("recovery-failed"),
        {"response_id": "response-1", "session_generation": 3},
        expected_session_generation=3,
    )

    for update in (stale, failed):
        assert update.remote_mutation_status in {"stale", "unknown"}
        assert update.continuation_allowed is False
        assert update.compacted_response_id is None
    assert stale_manager.calls == []
    assert failing_manager.calls == ["response-1"]


def test_remote_compaction_is_idempotent_for_one_recovery_id() -> None:
    manager = _Manager()
    port = ResponsesRecoveryPort(manager)
    session = {"response_id": "response-1", "session_generation": 7}

    first = port.apply(_remote_plan("recovery-idempotent"), session, 7)
    second = port.apply(_remote_plan("recovery-idempotent"), session, 7)

    assert first == second
    assert first.remote_mutation_status == "applied"
    assert first.session_generation == 8
    assert manager.calls == ["response-1"]


def test_remote_update_only_adopts_a_valid_compacted_continuation() -> None:
    core = type("Core", (), {"responses_state": {"provider": "openai", "model": "m"}})()
    applied = type(
        "Update",
        (),
        {
            "remote_mutation_status": "applied",
            "continuation_allowed": True,
            "compacted_response_id": "resp_compacted",
            "session_generation": 2,
        },
    )()
    rejected = type(
        "Update",
        (),
        {
            "remote_mutation_status": "stale",
            "continuation_allowed": False,
            "compacted_response_id": None,
            "session_generation": 2,
        },
    )()

    assert _apply_remote_recovery_update(core, applied)
    assert core.responses_state["previous_response_id"] == "resp_compacted"
    assert not _apply_remote_recovery_update(core, rejected)
    assert "previous_response_id" not in core.responses_state

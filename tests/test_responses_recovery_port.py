from __future__ import annotations

from dataclasses import dataclass, replace

from uagent.providers.responses_recovery_port import (
    InMemoryRecoveryJournal,
    ResponsesRecoveryPort,
    SQLiteRecoveryJournal,
)
from uagent.runtime.context_recovery import RecoveryPlan


@dataclass
class _Response:
    id: str


class _Manager:
    def __init__(self, response_id: str = "cmp_1") -> None:
        self.response_id = response_id
        self.calls: list[tuple[str, object]] = []

    def compact(self, response_id: str, *, input=None):
        self.calls.append((response_id, input))
        return _Response(self.response_id)


def _plan(recovery_id: str = "recovery-1") -> RecoveryPlan:
    return RecoveryPlan(
        recovery_id=recovery_id,
        plan_id="plan-1",
        projection_id="projection-1",
        classification="context_overflow",
        strategy="provider_compact",
        remote_session_mutation=True,
    )


def test_compact_applies_generation_and_journal_update_without_history_mutation() -> (
    None
):
    manager = _Manager()
    journal = InMemoryRecoveryJournal()
    port = ResponsesRecoveryPort(manager, journal=journal)
    provider_session = {
        "response_id": "resp_1",
        "session_generation": 4,
        "input": [{"role": "user", "content": "hello"}],
    }
    before = dict(provider_session)

    update = port.apply(_plan(), provider_session, expected_session_generation=4)

    assert manager.calls == [("resp_1", provider_session["input"])]
    assert update.session_generation == 5
    assert update.compacted_response_id == "cmp_1"
    assert update.remote_mutation_status == "applied"
    assert update.continuation_allowed is True
    assert update.journal_entry_id == "recovery:recovery-1"
    assert provider_session == before


def test_update_carries_identity_and_rejects_session_metadata_mismatch() -> None:
    manager = _Manager()
    port = ResponsesRecoveryPort(manager)
    plan = RecoveryPlan(
        recovery_id="recovery-metadata",
        plan_id="plan-1",
        projection_id="projection-1",
        classification="context_overflow",
        strategy="provider_compact",
        remote_session_mutation=True,
        input_fingerprint="fingerprint-1",
        history_revision="history-1",
        schema_revision="schema-1",
    )
    session = {
        "response_id": "resp_1",
        "session_generation": 4,
        "input_fingerprint": "fingerprint-1",
        "plan_id": "plan-1",
        "projection_id": "projection-1",
        "history_revision": "history-1",
        "schema_revision": "schema-1",
    }

    update = port.apply(plan, session, expected_session_generation=4)

    assert update.input_fingerprint == "fingerprint-1"
    assert update.plan_id == "plan-1"
    assert update.projection_id == "projection-1"
    assert update.history_revision == "history-1"
    assert update.schema_revision == "schema-1"

    stale = port.apply(
        replace(plan, recovery_id="recovery-metadata-stale"),
        {**session, "history_revision": "history-2"},
        expected_session_generation=4,
    )

    assert stale.remote_mutation_status == "stale"
    assert stale.continuation_allowed is False
    assert len(manager.calls) == 1


def test_generation_mismatch_is_stale_and_does_not_call_provider() -> None:
    manager = _Manager()
    port = ResponsesRecoveryPort(manager)

    update = port.apply(
        _plan(),
        {"response_id": "resp_1", "session_generation": 5},
        expected_session_generation=4,
    )

    assert manager.calls == []
    assert update.remote_mutation_status == "stale"
    assert update.continuation_allowed is False
    assert update.session_generation == 5


def test_same_recovery_id_is_idempotent() -> None:
    manager = _Manager()
    port = ResponsesRecoveryPort(manager)
    session = {"response_id": "resp_1", "session_generation": 1}

    first = port.apply(_plan(), session, expected_session_generation=1)
    second = port.apply(_plan(), session, expected_session_generation=1)

    assert first == second
    assert len(manager.calls) == 1


def test_non_compaction_plan_is_rejected_without_provider_call() -> None:
    manager = _Manager()
    port = ResponsesRecoveryPort(manager)
    plan = RecoveryPlan(
        recovery_id="recovery-2",
        plan_id="plan-1",
        projection_id=None,
        classification="stale_continuation",
        strategy="client_projection",
    )

    update = port.apply(plan, {"response_id": "resp_1"}, 0)

    assert manager.calls == []
    assert update.remote_mutation_status == "rejected"
    assert update.continuation_allowed is False


def test_sqlite_journal_preserves_idempotency_across_port_instances(tmp_path) -> None:
    journal_path = tmp_path / "recovery.sqlite3"
    manager = _Manager()
    with SQLiteRecoveryJournal(journal_path) as journal:
        first = ResponsesRecoveryPort(manager, journal=journal).apply(
            _plan("durable-1"),
            {"response_id": "resp_1", "session_generation": 1},
            expected_session_generation=1,
        )

    second_manager = _Manager("cmp_should_not_run")
    with SQLiteRecoveryJournal(journal_path) as journal:
        second = ResponsesRecoveryPort(second_manager, journal=journal).apply(
            _plan("durable-1"),
            {"response_id": "resp_1", "session_generation": 1},
            expected_session_generation=1,
        )

    assert second == first
    assert second_manager.calls == []


def test_provider_error_is_unknown_and_continuation_is_blocked() -> None:
    class FailingManager(_Manager):
        def compact(self, response_id: str, *, input=None):
            self.calls.append((response_id, input))
            raise RuntimeError("provider unavailable")

    manager = FailingManager()
    port = ResponsesRecoveryPort(manager)

    update = port.apply(_plan(), {"response_id": "resp_1"}, 0)

    assert update.remote_mutation_status == "unknown"
    assert update.continuation_allowed is False

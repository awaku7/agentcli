from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from uagent.runtime.compaction_record import (
    CompactionValidationError,
    DecisionRecord,
    ExecutionRecord,
    SourceRef,
)
from uagent.runtime.handoff_record import (
    HandoffRecord,
    ProvenancedDeterministicDelta,
    ProvenancedDeterministicItem,
    ProvenancedExecutionRecord,
    ProvenancedHandoffItem,
)


def _ref(kind="message", ref_id="answer", scope="sub-session", seq=1):
    return SourceRef(kind, ref_id, scope, seq)


def _record(**changes):
    values = dict(
        handoff_id="handoff-1",
        root_handoff_id="handoff-1",
        receiving_session_id="main-session",
        receiving_base_revision=7,
        application_base_revision=7,
        agent_id="worker-1",
        role="researcher",
        goal_ids=("goal-1",),
        objective="Investigate the failing check",
    )
    values.update(changes)
    return HandoffRecord(**values)


def test_roundtrip_preserves_item_provenance_and_dispatch_lineage():
    answer = _ref()
    event = _ref("event", "write", seq=2)
    execution = _ref("execution", "check", seq=3)
    artifact = SourceRef("artifact", "log", "workspace")
    item = ProvenancedHandoffItem("Fixed the regression", [answer])
    record = _record(
        work_done=[item],
        findings=[item],
        decisions=[DecisionRecord("d1", "Keep the public API", source_refs=[answer])],
        unresolved=[item],
        recommended_next_steps=[item],
        state_delta=ProvenancedDeterministicDelta(
            modified_files=[ProvenancedDeterministicItem("src/check.py", [event])],
            executed_checks=[
                ProvenancedExecutionRecord(
                    ExecutionRecord(
                        "pytest", "passed", exit_code=0, artifact_ref=artifact
                    ),
                    [execution],
                )
            ],
        ),
        artifact_refs=[artifact],
        source_checkpoint_id="checkpoint-1",
    )
    decoded = HandoffRecord.from_dict(json.loads(record.to_json()))
    assert decoded == record
    assert decoded.work_done[0].source_refs == (answer,)
    assert decoded.state_delta.modified_files[0].source_refs == (event,)
    assert decoded.state_delta.executed_checks[0].execution.artifact_ref == artifact
    assert all(
        item.status == "unavailable" for item in decoded.state_delta.tracking_coverage
    )
    assert decoded.receiving_base_revision == decoded.application_base_revision == 7


def test_input_lists_are_detached_and_record_is_immutable():
    refs = [_ref()]
    reports = [ProvenancedHandoffItem("Observed", refs)]
    record = _record(work_done=reports)
    refs.clear()
    reports.clear()
    assert len(record.work_done[0].source_refs) == 1
    with pytest.raises(FrozenInstanceError):
        record.receiving_base_revision = 8


def test_reconciliation_preserves_original_snapshot_and_root():
    original = _record()
    derivative = replace(original, handoff_id="handoff-2", application_base_revision=9)
    assert derivative.root_handoff_id == original.handoff_id
    assert derivative.receiving_base_revision == original.receiving_base_revision == 7
    assert original.application_base_revision == 7
    assert HandoffRecord.from_dict(derivative.to_dict()) == derivative


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"handoff_id": ""},
        {"objective": ""},
        {"role": 12},
        {"receiving_base_revision": -1},
        {"receiving_base_revision": True},
        {"application_base_revision": 8},
        {"handoff_id": "adjusted", "application_base_revision": 6},
        {"goal_ids": ["g"] * 51},
        {"findings": ["no provenance"]},
        {"state_delta": {}},
        {"artifact_refs": [_ref()]},
        {"objective": "invalid\x00control"},
        {"objective": "x" * 16001},
    ],
)
def test_invalid_metadata_and_untyped_payloads_are_rejected(changes):
    with pytest.raises(CompactionValidationError):
        _record(**changes)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ProvenancedHandoffItem("claim", []),
        lambda: ProvenancedDeterministicItem("path", []),
        lambda: ProvenancedExecutionRecord(ExecutionRecord("pytest", "passed"), []),
        lambda: ProvenancedDeterministicDelta(modified_files=["inferred.py"]),
        lambda: ProvenancedDeterministicDelta(
            executed_checks=[ExecutionRecord("pytest", "passed")]
        ),
        lambda: ProvenancedDeterministicDelta(tracking_coverage=[]),
    ],
)
def test_checkpoint_id_cannot_replace_item_level_evidence(factory):
    with pytest.raises(CompactionValidationError):
        factory()


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_history", [{"role": "user", "content": "private"}]),
        ("provider_response_id", "resp-private"),
        ("state_delta", {"raw_events": ["private"]}),
        ("work_done", [{"text": "claim", "source_refs": [], "raw_message": "private"}]),
    ],
)
def test_decoder_rejects_unknown_fields_including_nested_payloads(field, value):
    payload = _record().to_dict()
    payload[field] = value
    with pytest.raises(CompactionValidationError):
        HandoffRecord.from_dict(payload)


def test_aggregate_size_is_bounded_even_when_individual_items_are_valid():
    reports = [ProvenancedHandoffItem("日" * 16000, [_ref()]) for _ in range(22)]
    with pytest.raises(CompactionValidationError, match="byte budget"):
        _record(work_done=reports)

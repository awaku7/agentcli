from __future__ import annotations

import json

import pytest

from uagent.runtime.compaction_record import (
    CompactionRecord,
    CompactionValidationError,
    ConstraintRecord,
    DecisionRecord,
    DeterministicDelta,
    ExecutionRecord,
    FactRecord,
    GoalDelta,
    ProvenancedNarrativeItem,
    ProvenancedObservation,
    SCHEMA_VERSION,
    SourceRef,
    TrackingCoverage,
)


def _ref(
    ref_id: str,
    *,
    kind: str = "message",
    session_seq: int | None = None,
) -> SourceRef:
    if kind != "artifact" and session_seq is None:
        session_seq = int(ref_id.rsplit("_", 1)[-1])
    return SourceRef(
        kind=kind,
        ref_id=ref_id,
        scope_id="session_1",
        session_seq=session_seq,
    )


def _record(**overrides) -> CompactionRecord:
    values = {
        "record_id": "cmp_1",
        "operation_id": "op_1",
        "application_status": "applied",
        "session_id": "session_1",
        "actor_kind": "runtime",
        "actor_id": "runtime_1",
        "source_start_id": "message_10",
        "source_end_id": "message_18",
        "source_start_seq": 10,
        "source_end_seq": 18,
        "source_message_count": 9,
        "source_tokens": 1200,
        "source_chars": 4800,
        "base_revision": 4,
        "committed_revision": 5,
        "goal_deltas": (
            GoalDelta(
                goal_delta_id="op_1:goal_1",
                association="new",
                title_hint="Add compaction records",
                progress_events=(
                    ProvenancedObservation("Model created", (_ref("message_12"),)),
                ),
                decisions=(
                    DecisionRecord(
                        decision_id="decision_1",
                        decision="Use dataclasses",
                        source_refs=(_ref("message_13"),),
                    ),
                ),
                constraints=(
                    ConstraintRecord(
                        constraint_id="constraint_1",
                        constraint="Keep the current shrink path unchanged",
                        source_refs=(_ref("message_14"),),
                    ),
                ),
                facts=(
                    FactRecord(
                        "fact_1",
                        "SQLite is already used",
                        (_ref("event_1", kind="event"),),
                    ),
                ),
                source_refs=(_ref("message_12"),),
            ),
        ),
        "shared_facts": (
            FactRecord("fact_2", "Model is provider-neutral", (_ref("message_15"),)),
        ),
        "deterministic_delta": DeterministicDelta(
            read_files=("src/uagent/runtime/agent_state.py",),
            artifact_refs=(_ref("test-log", kind="artifact"),),
            tool_call_refs=(_ref("call_17", kind="tool_call"),),
            subagent_refs=(_ref("subagent_12", kind="subagent"),),
            pending_operation_events=(_ref("pending_17", kind="pending_operation"),),
            executed_checks=(
                ExecutionRecord(
                    command_class="pytest",
                    target="tests/test_compaction_record.py",
                    status="passed",
                    exit_code=0,
                    artifact_ref=_ref("test-log", kind="artifact"),
                ),
            ),
        ),
        "narrative_continuation": (
            ProvenancedNarrativeItem(
                "The existing rolling compactor remains unchanged.",
                (_ref("message_16"),),
            ),
        ),
        "summarizer_usage": {"input_tokens": 900, "output_tokens": 180},
    }
    values.update(overrides)
    return CompactionRecord(**values)


def test_source_ref_requires_scope_and_sequence_for_session_items() -> None:
    with pytest.raises(CompactionValidationError, match="session_seq"):
        SourceRef(kind="message", ref_id="message_1", scope_id="session_1")

    global_artifact = SourceRef(
        kind="artifact", ref_id="artifact_1", scope_id="workspace_1"
    )
    assert global_artifact.session_seq is None


def test_compaction_record_round_trips_nested_records_as_json() -> None:
    record = _record()

    restored = CompactionRecord.from_json(record.to_json())

    assert restored.to_dict() == record.to_dict()
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.goal_deltas[0].source_refs[0] == _ref("message_12")
    assert isinstance(restored.goal_deltas[0].source_refs[0], SourceRef)
    assert restored.goal_deltas[0].source_refs[0].session_seq == 12
    assert isinstance(restored.goal_deltas[0], GoalDelta)
    assert isinstance(
        restored.goal_deltas[0].progress_events[0], ProvenancedObservation
    )
    assert isinstance(restored.deterministic_delta.executed_checks[0], ExecutionRecord)
    assert all(
        isinstance(item, TrackingCoverage)
        for item in restored.deterministic_delta.tracking_coverage
    )
    assert {item.status for item in restored.deterministic_delta.tracking_coverage} == {
        "unavailable"
    }


def test_compaction_record_freezes_summarizer_metadata() -> None:
    record = _record()
    with pytest.raises(TypeError):
        record.summarizer_usage["input_tokens"] = 0
    assert record.to_dict()["summarizer_usage"]["input_tokens"] == 900


def test_goal_delta_validates_association_shape() -> None:
    with pytest.raises(CompactionValidationError, match="ambiguous GoalDelta"):
        GoalDelta(
            goal_delta_id="d1",
            association="ambiguous",
            goal_id="goal_1",
        )

    with pytest.raises(CompactionValidationError, match="requires title_hint"):
        GoalDelta(goal_delta_id="d2", association="new")

    with pytest.raises(CompactionValidationError, match="invalid goal association"):
        GoalDelta(goal_delta_id="d3", association=[], source_refs=(_ref("message_1"),))

    with pytest.raises(CompactionValidationError, match="at least one"):
        ProvenancedObservation("unproven observation", ())


def test_applied_record_requires_revision_consistency() -> None:
    with pytest.raises(CompactionValidationError, match="source sequence range"):
        _record(source_start_seq=None, source_end_seq=None)

    with pytest.raises(CompactionValidationError, match="must not precede"):
        _record(source_start_seq=19)

    with pytest.raises(CompactionValidationError, match="requires base_revision"):
        _record(base_revision=None)

    with pytest.raises(CompactionValidationError, match=r"base_revision \+ 1"):
        _record(committed_revision=7)


def test_comparison_only_record_never_claims_committed_revision() -> None:
    with pytest.raises(
        CompactionValidationError, match="must not have committed_revision"
    ):
        _record(application_status="comparison_only")

    with pytest.raises(CompactionValidationError, match="requires base_revision"):
        _record(
            application_status="comparison_only",
            committed_revision=None,
            base_revision=None,
        )

    comparison = _record(
        application_status="comparison_only",
        committed_revision=None,
    )
    assert comparison.base_revision == 4
    assert comparison.committed_revision is None


def test_parser_rejects_unknown_schema_and_fields() -> None:
    payload = _record().to_dict()
    payload["schema_version"] = SCHEMA_VERSION + 1
    with pytest.raises(CompactionValidationError, match="unsupported"):
        CompactionRecord.from_dict(payload)

    payload = _record().to_dict()
    payload.pop("schema_version")
    with pytest.raises(CompactionValidationError, match="schema_version is required"):
        CompactionRecord.from_dict(payload)

    payload = _record().to_dict()
    payload["unexpected"] = True
    with pytest.raises(
        CompactionValidationError, match="unknown CompactionRecord fields"
    ):
        CompactionRecord.from_dict(payload)


def test_parser_rejects_invalid_json_and_oversized_sections() -> None:
    with pytest.raises(
        CompactionValidationError, match="invalid CompactionRecord JSON"
    ):
        CompactionRecord.from_json("{")

    payload = _record().to_dict()
    payload["goal_deltas"] = payload["goal_deltas"] * 51
    with pytest.raises(CompactionValidationError, match="exceeds 50 items"):
        CompactionRecord.from_dict(payload)


def test_deterministic_file_lists_remove_duplicates_and_keep_order() -> None:
    delta = DeterministicDelta(
        read_files=("src/a.py", "src/b.py", "src/a.py"),
    )

    assert delta.read_files == ("src/a.py", "src/b.py")


def test_tracking_coverage_is_explicit_and_complete_by_dimension() -> None:
    with pytest.raises(CompactionValidationError, match="each tracking dimension"):
        DeterministicDelta(tracking_coverage=())

    with pytest.raises(CompactionValidationError, match="requires observed_by"):
        TrackingCoverage(dimension="file_reads", status="partial")

    completed = TrackingCoverage(
        dimension="file_reads",
        status="complete",
        observed_by=("file_tool",),
    )
    assert completed.observed_by == ("file_tool",)


def test_record_to_json_rejects_nan_in_usage_metadata() -> None:
    with pytest.raises(CompactionValidationError, match="non-finite"):
        _record(summarizer_usage={"score": float("nan")})


def test_from_dict_rejects_non_object_payload() -> None:
    with pytest.raises(CompactionValidationError, match="must be an object"):
        CompactionRecord.from_dict(json.loads("[]"))

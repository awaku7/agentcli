from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest

from uagent.runtime.compaction_record import (
    CompactionValidationError,
    ConstraintRecord,
    DecisionRecord,
    ExecutionRecord,
    SourceRef,
)
from uagent.runtime.handoff_projection import (
    HandoffBounds,
    project_main_to_sub_agent,
    project_sub_agent_return,
)
from uagent.runtime.handoff_record import (
    HandoffRecord,
    ProvenancedDeterministicDelta,
    ProvenancedDeterministicItem,
    ProvenancedExecutionRecord,
    ProvenancedHandoffItem,
)

REF = SourceRef("message", "m1", "sub-session", 1)
ARTIFACT = SourceRef("artifact", "a1", "workspace")
CHECKPOINT = SourceRef("checkpoint", "cp1", "sub-session", 2)


def _bounds(**changes):
    values = dict(
        receiving_session_id="main",
        receiving_base_revision=3,
        goal_ids=("g1",),
        source_refs=(REF, ARTIFACT, CHECKPOINT),
    )
    values.update(changes)
    return HandoffBounds(**values)


def _record(**changes):
    values = dict(
        handoff_id="h1",
        root_handoff_id="h1",
        receiving_session_id="main",
        receiving_base_revision=3,
        application_base_revision=3,
        agent_id="worker",
        role="researcher",
        goal_ids=("g1",),
        objective="Inspect the regression",
        findings=(ProvenancedHandoffItem("Root cause found", (REF,)),),
    )
    values.update(changes)
    return HandoffRecord(**values)


def _state():
    return {
        "raw_history": "PRIVATE HISTORY",
        "memory": "PRIVATE MEMORY",
        "provider_response_id": "PRIVATE PROVIDER STATE",
        "structured_compaction": {
            "schema_version": 1,
            "narrative_continuation": "PRIVATE GLOBAL NARRATIVE",
            "deterministic": {"modified_files": ["PRIVATE FILE"]},
            "goals": {
                "g1": {
                    "title": "Fix regression",
                    "progress_events": [
                        {
                            "text": "Investigated",
                            "source_refs": [REF.to_dict()],
                            "_operation_id": "internal-operation",
                            "raw_history": "PRIVATE GOAL HISTORY",
                        }
                    ],
                    "constraints": {
                        "c1": ConstraintRecord(
                            "c1", "Keep API stable", source_refs=(REF,)
                        ).to_dict()
                    },
                    "provider_cache_id": "PRIVATE CACHE",
                },
                "g2": {"title": "PRIVATE UNRELATED GOAL"},
            },
        },
    }


def _main(state=None, **changes):
    kwargs = dict(
        objective="Inspect regression",
        task_scope="Read-only investigation",
        goal_ids=("g1",),
        bounds=_bounds(),
        source_access_check=lambda ref: True,
    )
    kwargs.update(changes)
    return project_main_to_sub_agent(_state() if state is None else state, **kwargs)


def _return(record=None, **changes):
    kwargs = dict(bounds=_bounds(), source_access_check=lambda ref: True)
    kwargs.update(changes)
    return project_sub_agent_return(_record() if record is None else record, **kwargs)


def test_main_projection_only_contains_selected_goal_and_explicit_resources():
    state = _state()
    before = copy.deepcopy(state)
    payload = _main(state, checkpoint_refs=(CHECKPOINT,), artifact_refs=(ARTIFACT,))
    assert "PRIVATE" not in payload
    assert "internal-operation" not in payload
    parsed = json.loads(payload)
    assert [goal["goal_id"] for goal in parsed["goals"]] == ["g1"]
    assert parsed["goals"][0]["progress_events"][0]["source_refs"] == [REF.to_dict()]
    assert parsed["checkpoint_refs"] == [CHECKPOINT.to_dict()]
    assert parsed["artifact_refs"] == [ARTIFACT.to_dict()]
    assert parsed["receiving_base_revision"] == parsed["application_base_revision"] == 3
    assert state == before


def test_compact_return_is_stable_across_deliveries_and_contains_no_history():
    record = _record(artifact_refs=(ARTIFACT,), source_checkpoint_id="cp1")
    first = _return(record)
    assert first == _return(record)
    assert json.loads(first)["root_handoff_id"] == "h1"
    assert "raw_history" not in first
    assert json.loads(first)["findings"][0]["source_refs"] == [REF.to_dict()]


@pytest.mark.parametrize(
    "different_ref",
    [
        replace(REF, scope_id="other-session"),
        replace(REF, ref_id="ungranted-message"),
        replace(REF, session_seq=9),
        replace(REF, kind="event"),
    ],
)
def test_scope_or_id_alone_never_authorizes_a_reference(different_ref):
    record = _record(findings=(ProvenancedHandoffItem("Secret", (different_ref,)),))
    with pytest.raises(CompactionValidationError, match="unauthorized"):
        _return(record)


@pytest.mark.parametrize("render", [_main, _return])
def test_allowlist_is_an_upper_bound_and_current_access_is_rechecked(render):
    checked = []

    def unavailable(ref):
        checked.append(ref)
        return False

    with pytest.raises(CompactionValidationError, match="unavailable"):
        render(source_access_check=unavailable)
    assert REF in checked


@pytest.mark.parametrize("render", [_main, _return])
def test_empty_source_grant_fails_closed(render):
    with pytest.raises(CompactionValidationError, match="unauthorized"):
        render(bounds=_bounds(source_refs=()))


@pytest.mark.parametrize("render", [_main, _return])
def test_unrelated_goals_are_rejected(render):
    with pytest.raises(CompactionValidationError, match="out-of-scope goal"):
        render(bounds=_bounds(goal_ids=()))


@pytest.mark.parametrize(
    "changes",
    [
        {"receiving_session_id": "other-main"},
        {"receiving_base_revision": 2},
    ],
)
def test_return_is_bound_to_original_receiver_and_dispatch_revision(changes):
    with pytest.raises(CompactionValidationError, match="dispatch snapshot"):
        _return(bounds=_bounds(**changes))


def test_reconciled_return_preserves_dispatch_revision_without_applying_state():
    record = _record(handoff_id="h2", application_base_revision=5)
    payload = json.loads(_return(record))
    assert payload["receiving_base_revision"] == 3
    assert payload["application_base_revision"] == 5
    assert payload["root_handoff_id"] == "h1"


def test_execution_artifact_and_deterministic_sources_are_also_checked():
    record = _record(
        state_delta=ProvenancedDeterministicDelta(
            modified_files=(ProvenancedDeterministicItem("file.py", (REF,)),),
            executed_checks=(
                ProvenancedExecutionRecord(
                    ExecutionRecord("pytest", "passed", artifact_ref=ARTIFACT), (REF,)
                ),
            ),
        )
    )
    with pytest.raises(CompactionValidationError, match="unauthorized"):
        _return(record, bounds=_bounds(source_refs=(REF,)))
    checked = []

    def authorize(ref):
        checked.append(ref)
        return True

    assert json.loads(_return(record, source_access_check=authorize))["state_delta"][
        "modified_files"
    ][0]["source_refs"] == [REF.to_dict()]
    assert ARTIFACT in checked


def test_checkpoint_id_is_neither_a_capability_nor_a_substitute_for_item_sources():
    with pytest.raises(CompactionValidationError, match="scoped reference"):
        _return(_record(source_checkpoint_id="cp-private"))
    with pytest.raises(CompactionValidationError, match="unauthorized"):
        _return(
            _record(source_checkpoint_id="cp1"),
            bounds=_bounds(source_refs=(CHECKPOINT,)),
        )


@pytest.mark.parametrize("render", [_main, _return])
def test_budget_rejects_oversize_json_without_truncating_provenance(render):
    full = render()
    size = len(full.encode("utf-8"))
    assert render(bounds=_bounds(max_bytes=size)) == full
    with pytest.raises(CompactionValidationError, match="byte budget"):
        render(bounds=_bounds(max_bytes=size - 1))


def test_utf8_budget_counts_bytes_not_characters():
    record = _record(objective="日本語の調査")
    payload = _return(record)
    with pytest.raises(CompactionValidationError, match="byte budget"):
        _return(record, bounds=_bounds(max_bytes=len(payload)))


@pytest.mark.parametrize(
    "changes",
    [
        {"max_bytes": 0},
        {"max_bytes": 128001},
        {"max_bytes": True},
        {"receiving_base_revision": True},
        {"source_refs": ["untyped"]},
    ],
)
def test_invalid_caller_bounds_are_rejected(changes):
    with pytest.raises(CompactionValidationError):
        _bounds(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"checkpoint_refs": (ARTIFACT,)},
        {"artifact_refs": (CHECKPOINT,)},
        {"constraints": ("untyped",)},
        {"objective": "bad\x00text"},
        {"task_scope": ""},
        {"goal_ids": ("unknown",), "bounds": _bounds(goal_ids=("unknown",))},
    ],
)
def test_main_projection_rejects_invalid_resource_types_and_scope(changes):
    with pytest.raises(CompactionValidationError):
        _main(**changes)


def test_unknown_state_schema_is_not_projected():
    state = _state()
    state["structured_compaction"]["schema_version"] = 2
    with pytest.raises(CompactionValidationError, match="schema"):
        _main(state)


def test_no_goals_does_not_fall_back_to_global_state_or_history():
    payload = _main(goal_ids=())
    assert json.loads(payload)["goals"] == []
    assert "PRIVATE" not in payload


@pytest.mark.parametrize(
    "section", ["status_observations", "progress_events", "next_action_observations"]
)
def test_accumulated_goal_observations_are_selected_without_mutating_state(section):
    state = _state()
    goal = state["structured_compaction"]["goals"]["g1"]
    goal[section] = [
        {"text": f"Observation {index}", "source_refs": [REF.to_dict()]}
        for index in range(75)
    ]
    before = copy.deepcopy(state)
    projected = json.loads(_main(state))["goals"][0]
    assert len(projected[section]) == 50
    assert projected[section][0]["text"] == "Observation 25"
    assert projected[section][-1]["text"] == "Observation 74"
    assert projected["omitted_evidence"] == {section: 25}
    assert all(item["source_refs"] == [REF.to_dict()] for item in projected[section])
    assert state == before


@pytest.mark.parametrize(
    "section,record_type,text_field,id_field,inactive",
    [
        ("decisions", DecisionRecord, "decision", "decision_id", "superseded"),
        ("constraints", ConstraintRecord, "constraint", "constraint_id", "revoked"),
    ],
)
def test_lifecycle_selection_prefers_current_items_to_inactive_history(
    section, record_type, text_field, id_field, inactive
):
    state = _state()
    goal = state["structured_compaction"]["goals"]["g1"]
    goal[section] = {
        f"item-{index}": record_type(
            **{
                id_field: f"item-{index}",
                text_field: f"Evidence {index}",
                "status": "active" if index == 0 else inactive,
                "source_refs": (REF,),
            }
        ).to_dict()
        for index in range(51)
    }
    before = copy.deepcopy(state)
    projected = json.loads(_main(state))["goals"][0]
    assert len(projected[section]) == 50
    assert any(item[id_field] == "item-0" for item in projected[section])
    assert projected["omitted_evidence"] == {section: 1}
    assert state == before


def test_unselected_old_sources_are_not_disclosed_or_reauthorized():
    state = _state()
    observations = [
        {"text": f"Observation {index}", "source_refs": [REF.to_dict()]}
        for index in range(50)
    ]
    observations.insert(
        0,
        {
            "text": "PRIVATE OLD SOURCE",
            "source_refs": [replace(REF, ref_id="revoked-message").to_dict()],
        },
    )
    state["structured_compaction"]["goals"]["g1"]["progress_events"] = observations
    payload = _main(state)
    assert "PRIVATE" not in payload
    assert "revoked-message" not in payload
    assert json.loads(payload)["goals"][0]["omitted_evidence"] == {"progress_events": 1}


def test_return_can_authorize_distinct_sources_across_multiple_valid_sections():
    refs = tuple(
        replace(REF, ref_id=f"m{index}", session_seq=index + 1) for index in range(51)
    )
    record = _record(
        work_done=tuple(
            ProvenancedHandoffItem(f"Work {index}", (ref,))
            for index, ref in enumerate(refs[:26])
        ),
        findings=tuple(
            ProvenancedHandoffItem(f"Finding {index}", (ref,))
            for index, ref in enumerate(refs[26:])
        ),
    )
    bounds = _bounds(source_refs=refs)
    assert len(bounds.source_refs) == 51
    payload = _return(record, bounds=bounds)
    assert HandoffRecord.from_dict(json.loads(payload)) == record
    with pytest.raises(CompactionValidationError, match="unauthorized"):
        _return(record, bounds=_bounds(source_refs=refs[:-1]))


def test_main_can_authorize_distinct_sources_across_goal_sections():
    state = _state()
    goal = state["structured_compaction"]["goals"]["g1"]
    refs = tuple(
        replace(REF, ref_id=f"m{index}", session_seq=index + 1) for index in range(51)
    )
    goal["constraints"] = {}
    goal["progress_events"] = [
        {"text": "Done", "source_refs": [ref.to_dict()]} for ref in refs[:26]
    ]
    goal["next_action_observations"] = [
        {"text": "Next", "source_refs": [ref.to_dict()]} for ref in refs[26:]
    ]
    checked = set()

    def authorize(ref):
        checked.add(ref)
        return True

    payload = _main(
        state, bounds=_bounds(source_refs=refs), source_access_check=authorize
    )
    projected = json.loads(payload)["goals"][0]
    assert len(projected["progress_events"]) == 26
    assert len(projected["next_action_observations"]) == 25
    assert checked == set(refs)

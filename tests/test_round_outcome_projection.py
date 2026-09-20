from __future__ import annotations

from uagent.runtime.round_outcome import (
    project_round_outcome,
    round_outcome_event,
    round_outcome_key,
)


def test_project_round_outcome_detaches_mapping_and_normalizes_keys() -> None:
    source = {"round": 2, "status": "completed", "reason": "regex"}

    projected = project_round_outcome(source)
    source["reason"] = "changed"

    assert projected == {"round": 2, "status": "completed", "reason": "regex"}
    assert project_round_outcome(None) == {}
    assert project_round_outcome([]) == {}


def test_round_outcome_event_uses_common_host_envelope() -> None:
    assert round_outcome_event({"round": 1, "status": "failed"}) == {
        "type": "round_outcome",
        "round": 1,
        "status": "failed",
    }
    assert round_outcome_event({}) == {}


def test_round_outcome_key_suppresses_duplicate_host_updates() -> None:
    value = {"round": 3, "status": "completed", "reason": "reviewer"}

    assert round_outcome_key(value) == (3, "completed", "reviewer")
    assert round_outcome_key({"round": 3, "status": "completed"}) == (
        3,
        "completed",
        None,
    )

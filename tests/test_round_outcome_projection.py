from __future__ import annotations

from uagent.runtime.round_contracts import RoundIdentifiers, RoundResult, RoundSummary
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


def test_project_round_outcome_accepts_provider_neutral_result() -> None:
    result = RoundResult(
        identifiers=RoundIdentifiers(
            "turn", "round-2", "attempt", "request", "stream", 1
        ),
        plan_id="plan",
        projection_id="projection",
        status="continue",
        assistant_text="partial",
        tool_calls=({"id": "call-1"},),
        summary=RoundSummary(
            status="continue",
            tool_call_count=1,
            assistant_chars=7,
        ),
    )

    projected = project_round_outcome(result)

    assert projected["round"] == "round-2"
    assert projected["status"] == "continue"
    assert projected["tool_calls"] == 1
    assert projected["summary"]["tool_call_count"] == 1
    assert "assistant_text" not in projected

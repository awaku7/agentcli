from __future__ import annotations

import pytest

from uagent.runtime.agent_state import AgentState, AgentStateManager


def test_agent_state_round_trips_as_json() -> None:
    state = AgentState(
        goal="ship feature",
        completed_steps=("design",),
        current_step="implement",
        files=("src/app.py",),
        errors=(),
        next_action="run tests",
        mcp_request_generation=4,
    )

    restored = AgentState.from_dict(state.to_dict())

    assert restored.goal == "ship feature"
    assert restored.completed_steps == ("design",)
    assert restored.failed_steps == ()
    assert restored.mcp_request_generation == 4
    assert restored.to_json() == state.to_json()


def test_manager_updates_progress_without_duplicates() -> None:
    manager = AgentStateManager()

    manager.update(goal="ship feature", current_step="implement")
    manager.mark_step_complete("implement", next_action="test")
    manager.mark_step_complete("implement")
    manager.add_file("src/app.py")
    manager.add_file("src/app.py")
    manager.add_error("test failed")

    assert manager.state.completed_steps == ("implement",)
    assert manager.state.current_step == ""
    assert manager.state.next_action == ""
    assert manager.state.files == ("src/app.py",)
    assert manager.state.errors == ("test failed",)


def test_failed_step_is_not_completed_and_retry_can_clear_failure() -> None:
    manager = AgentStateManager()

    manager.mark_step_complete("tool:fetch_url")
    manager.mark_step_failed("tool:fetch_url")
    manager.mark_step_failed("tool:fetch_url")

    assert manager.state.completed_steps == ()
    assert manager.state.failed_steps == ("tool:fetch_url",)
    assert AgentState.from_dict(manager.state.to_dict()).failed_steps == (
        "tool:fetch_url",
    )

    manager.mark_step_complete("tool:fetch_url")
    assert manager.state.completed_steps == ("tool:fetch_url",)
    assert manager.state.failed_steps == ()


def test_manager_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        AgentStateManager().update(unknown="value")

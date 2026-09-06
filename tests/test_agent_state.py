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
    )

    restored = AgentState.from_dict(state.to_dict())

    assert restored.goal == "ship feature"
    assert restored.completed_steps == ("design",)
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


def test_manager_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        AgentStateManager().update(unknown="value")

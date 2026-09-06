from __future__ import annotations

from types import SimpleNamespace

from uagent.uagent_llm import _update_agent_state_for_turn


def test_agent_state_is_updated_from_user_turn() -> None:
    saved: dict[str, str] = {}
    core = SimpleNamespace(
        get_agent_state=lambda: {},
        update_agent_state=lambda **changes: saved.update(changes),
    )
    messages = [{"role": "user", "content": "ship the feature"}]

    assert _update_agent_state_for_turn(messages, core) is True
    assert saved == {"current_step": "llm_round", "goal": "ship the feature"}


def test_existing_goal_is_preserved() -> None:
    saved: dict[str, str] = {}
    core = SimpleNamespace(
        get_agent_state=lambda: {"goal": "original goal"},
        update_agent_state=lambda **changes: saved.update(changes),
    )

    assert (
        _update_agent_state_for_turn([{"role": "user", "content": "continue"}], core)
        is True
    )
    assert saved == {"current_step": "llm_round"}

from __future__ import annotations

from types import SimpleNamespace

from uagent.uagent_llm import _inject_agent_state_context


def test_agent_state_is_injected_once() -> None:
    messages = [{"role": "user", "content": "continue the task"}]
    core = SimpleNamespace(
        get_agent_state=lambda: {
            "goal": "ship feature",
            "current_step": "tool:read_file",
            "completed_steps": ["tool:search"],
            "next_action": "run tests",
        }
    )

    assert _inject_agent_state_context(messages, core) is True
    assert "[agent state]" in messages[0]["content"]
    assert "ship feature" in messages[0]["content"]
    assert _inject_agent_state_context(messages, core) is False

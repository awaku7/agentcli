from __future__ import annotations

from types import SimpleNamespace

from uagent.uagent_llm import _format_agent_state_context, _inject_agent_state_context


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


def test_agent_state_preserves_structured_fields_and_budget() -> None:
    messages = [{"role": "user", "content": "continue"}]
    core = SimpleNamespace(
        context_policy=SimpleNamespace(
            auto_state=True, budget_unlimited=False, budget_chars=120
        ),
        get_agent_state=lambda: {
            "goal": "ship feature",
            "current_step": "implementation",
            "next_action": "run tests",
            "known_facts": ["fact-1"],
            "pending_tasks": ["task-1"],
            "decisions": ["decision-1"],
        },
    )

    assert _inject_agent_state_context(messages, core) is True
    assert "[agent state]" in messages[0]["content"]
    assert len(messages[0]["content"].split("\n\n", 1)[0]) <= 120


def test_agent_state_projection_includes_recent_failed_steps() -> None:
    state = {
        "goal": "recover a failed operation",
        "completed_steps": ["tool:read_file"],
        "failed_steps": [f"tool:failed-{index}" for index in range(25)],
    }
    rendered = _format_agent_state_context(state)
    assert "failed_steps: tool:failed-5" in rendered
    assert "tool:failed-24" in rendered
    assert "tool:failed-4" not in rendered
    assert "completed_steps: tool:read_file" in rendered

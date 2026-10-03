from __future__ import annotations

import json

from uagent.decision import DecisionSettings
from uagent.runtime import sub_agent_autonomy
from uagent.tools import sub_agent_chain_tool, sub_agent_tool


def _general_json(summary: str) -> str:
    return json.dumps(
        {
            "status": "completed",
            "role": "general",
            "summary": summary,
            "details": {"value": summary},
            "notes": "",
        }
    )


def _disable_decision_provider(monkeypatch):
    monkeypatch.setattr(
        sub_agent_autonomy,
        "get_decision_settings",
        lambda: DecisionSettings(provider="none", source="test"),
    )


def test_sub_agent_continues_agent_round_from_llm_review(monkeypatch):
    _disable_decision_provider(monkeypatch)
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        sub_agent_tool,
        "make_client",
        lambda _cb: ("openai", object(), "test-model"),
    )

    work_outputs = iter([_general_json("partial"), _general_json("finished")])
    reviews = iter(["CONTINUE: missing validation", "COMPLETE"])
    work_prompts = []

    def fake_call(
        provider,
        client,
        model_name,
        system_prompt,
        user_prompt,
        timeout,
        max_retries,
        response_mode,
    ):
        if system_prompt.startswith("You are a conservative completion reviewer"):
            return (
                next(reviews),
                0,
                {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            )
        work_prompts.append(user_prompt)
        return (
            next(work_outputs),
            0,
            {
                "prompt_tokens": 2,
                "completion_tokens": 2,
                "total_tokens": 4,
            },
        )

    monkeypatch.setattr(runner, "_call_with_retry", fake_call)

    result = runner.run(
        "general",
        "finish and validate the task",
        response_mode="json",
        max_agent_rounds=3,
    )

    assert json.loads(result)["summary"] == "finished"
    assert len(work_prompts) == 2
    assert "missing validation" in work_prompts[1]
    assert "partial" in work_prompts[1]


def test_sub_agent_max_agent_rounds_limits_total_work_rounds(monkeypatch):
    _disable_decision_provider(monkeypatch)
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        sub_agent_tool,
        "make_client",
        lambda _cb: ("openai", object(), "test-model"),
    )

    work_count = 0
    review_count = 0

    def fake_call(
        provider,
        client,
        model_name,
        system_prompt,
        user_prompt,
        timeout,
        max_retries,
        response_mode,
    ):
        nonlocal work_count, review_count
        if system_prompt.startswith("You are a conservative completion reviewer"):
            review_count += 1
            return "CONTINUE: more work", 0, {}
        work_count += 1
        return _general_json(f"round-{work_count}"), 0, {}

    monkeypatch.setattr(runner, "_call_with_retry", fake_call)

    result = runner.run(
        "general",
        "keep working",
        response_mode="json",
        max_agent_rounds=2,
    )

    obj = json.loads(result)
    assert obj["status"] == "blocked"
    assert obj["reason"] == "max_rounds"
    assert obj["agent_rounds"] == 2
    assert obj["partial_result"]["status"] == "completed"
    assert obj["partial_result"]["summary"] == "round-2"
    assert work_count == 2
    assert review_count == 2


def test_sub_agent_completion_regex_skips_other_judges(monkeypatch):
    _disable_decision_provider(monkeypatch)
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        sub_agent_tool,
        "make_client",
        lambda _cb: ("openai", object(), "test-model"),
    )
    calls = []

    def fake_call(
        provider,
        client,
        model_name,
        system_prompt,
        user_prompt,
        timeout,
        max_retries,
        response_mode,
    ):
        calls.append(system_prompt)
        return "STATUS: DONE", 0, {}

    monkeypatch.setattr(runner, "_call_with_retry", fake_call)

    result = runner.run(
        "general",
        "finish",
        response_mode="text",
        completion_regex=r"DONE$",
        max_agent_rounds=5,
    )

    assert result == "STATUS: DONE"
    assert len(calls) == 1


def test_sub_agent_sentinel_is_completion_path(monkeypatch):
    _disable_decision_provider(monkeypatch)
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        sub_agent_tool,
        "make_client",
        lambda _cb: ("openai", object(), "test-model"),
    )
    calls = []

    def fake_call(
        provider,
        client,
        model_name,
        system_prompt,
        user_prompt,
        timeout,
        max_retries,
        response_mode,
    ):
        calls.append(system_prompt)
        return "finished\n<SUB_AGENT_COMPLETE>", 0, {}

    monkeypatch.setattr(runner, "_call_with_retry", fake_call)

    result = runner.run(
        "general",
        "finish",
        response_mode="text",
        completion_sentinel=True,
        max_agent_rounds=5,
    )

    assert result == "finished"
    assert len(calls) == 1


def test_sub_agent_tool_turn_budget_is_separate_from_agent_rounds(monkeypatch):
    _disable_decision_provider(monkeypatch)
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        sub_agent_tool,
        "make_client",
        lambda _cb: ("openai", object(), "test-model"),
    )
    tool_turn_budgets = []

    def fake_multi_turn(**kwargs):
        tool_turn_budgets.append(kwargs["max_turns"])
        return (
            "tool-backed answer",
            0,
            {},
            [
                {
                    "tool": "read_file",
                    "status": "success",
                    "summary": "observed",
                }
            ],
        )

    def fake_call(
        provider,
        client,
        model_name,
        system_prompt,
        user_prompt,
        timeout,
        max_retries,
        response_mode,
    ):
        return "COMPLETE", 0, {}

    monkeypatch.setattr(runner, "_run_llm_multi_turn", fake_multi_turn)
    monkeypatch.setattr(runner, "_call_with_retry", fake_call)

    result = runner.run(
        "general",
        "inspect",
        response_mode="text",
        permission_level="read_only",
        max_tool_turns=7,
        max_agent_rounds=4,
    )

    assert result == "tool-backed answer"
    assert tool_turn_budgets == [7]



def test_sub_agent_invalid_sentinel_is_reported_as_blocked(monkeypatch):
    _disable_decision_provider(monkeypatch)
    runner = sub_agent_tool.SubAgentRunner()
    monkeypatch.setattr(
        sub_agent_tool,
        "make_client",
        lambda _cb: ("openai", object(), "test-model"),
    )

    monkeypatch.setattr(
        runner,
        "_call_with_retry",
        lambda *args, **kwargs: ("finished without marker", 0, {}),
    )

    result = runner.run(
        "general",
        "finish",
        response_mode="text",
        completion_sentinel=True,
        max_agent_rounds=3,
    )

    obj = json.loads(result)
    assert obj["status"] == "blocked"
    assert obj["reason"] == "sentinel_invalid"
    assert obj["agent_rounds"] == 1
    assert obj["partial_result"] == "finished without marker"


def test_sub_agent_chain_stops_on_incomplete_sub_agent(monkeypatch):
    calls = []

    def fake_sub_agent(args):
        calls.append(args["task"])
        if len(calls) == 1:
            return json.dumps(
                {
                    "status": "blocked",
                    "reason": "max_rounds",
                    "message": "Sub-Agent reached max_agent_rounds before completion.",
                    "partial_result": {
                        "status": "completed",
                        "summary": "still incomplete",
                    },
                }
            )
        return _general_json("should not run")

    monkeypatch.setattr(sub_agent_tool, "run_tool", fake_sub_agent)

    raw = sub_agent_chain_tool.run_tool(
        {
            "chain": [
                {"agent_name": "general", "task": "first"},
                {"agent_name": "general", "task": "second"},
            ],
            "stop_on_error": True,
        }
    )

    result = json.loads(raw)
    assert result["status"] == "error"
    assert result["total_steps"] == 1
    assert result["steps"][0]["status"] == "blocked"
    assert calls == ["first"]

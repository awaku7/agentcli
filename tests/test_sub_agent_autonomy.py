from __future__ import annotations

from types import SimpleNamespace


from uagent.decision import DecisionAnswer, DecisionResult, DecisionSettings
from uagent.runtime import sub_agent_autonomy as autonomy


def test_sentinel_protocol_and_strip():
    assert autonomy.sentinel_judgment("done\n<SUB_AGENT_COMPLETE>") == "COMPLETE"
    assert autonomy.sentinel_judgment("more\nSUB_AGENT_CONTINUE") == "CONTINUE"
    assert autonomy.sentinel_judgment("done") is None
    assert autonomy.strip_sentinel("done\n<SUB_AGENT_COMPLETE>\n") == "done"


def test_regex_completion_is_optional_and_invalid_regex_is_safe():
    assert autonomy.completion_regex_matches("STATUS: DONE", r"DONE$")
    assert not autonomy.completion_regex_matches("STATUS: WORKING", r"DONE$")
    assert not autonomy.completion_regex_matches("anything", r"[")


def test_build_state_masks_secrets_and_bounds_evidence():
    state = autonomy.build_sub_agent_completion_state(
        "inspect token: goal-secret",
        "done token: answer-secret",
        prior_answers=[f"prior {i}" for i in range(8)],
        tool_evidence=[
            {
                "tool": "read_file",
                "status": "success",
                "summary": f"tool {i} token: tool-secret-{i}",
            }
            for i in range(8)
        ],
    )

    rendered = str(state)
    assert "goal-secret" not in rendered
    assert "answer-secret" not in rendered
    assert "tool-secret" not in rendered
    assert len([x for x in state["evidence"] if x["source"] == "assistant"]) == 4
    assert len([x for x in state["evidence"] if x["source"] == "tool"]) == 4


def test_reviewer_parser_is_conservative():
    assert autonomy.parse_reviewer_judgment("COMPLETE.") == ("COMPLETE", "")
    assert autonomy.parse_reviewer_judgment("not COMPLETE") == (
        "CONTINUE",
        "not COMPLETE",
    )
    assert autonomy.parse_reviewer_judgment("CONTINUE: missing tests") == (
        "CONTINUE",
        "missing tests",
    )
    assert autonomy.parse_reviewer_judgment("unclear") == ("CONTINUE", "unclear")


def test_sentinel_mode_is_exclusive_and_invalid_marker_stops(monkeypatch):
    monkeypatch.setattr(
        autonomy,
        "get_decision_settings",
        lambda: DecisionSettings(provider="none", source="default"),
    )
    reviewer_calls = []
    judge = autonomy.SubAgentCompletionJudge(
        reviewer=lambda state: reviewer_calls.append(state) or ("COMPLETE", ""),
        sentinel_enabled=True,
    )

    outcome = judge.judge(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        raw_output="no marker",
    )

    assert outcome.terminal_reason == "sentinel_invalid"
    assert reviewer_calls == []


def test_disabled_decision_provider_uses_llm_reviewer(monkeypatch):
    monkeypatch.setattr(
        autonomy,
        "get_decision_settings",
        lambda: DecisionSettings(provider="none", source="default"),
    )
    judge = autonomy.SubAgentCompletionJudge(
        reviewer=lambda state: ("CONTINUE", "missing validation"),
    )

    outcome = judge.judge(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        raw_output="y",
    )

    assert outcome.complete is False
    assert outcome.source == "llm_reviewer"
    assert outcome.feedback == "missing validation"


def test_decision_provider_complete_skips_llm_reviewer(monkeypatch):
    provider = SimpleNamespace(
        name="typesafe",
        model="jev-test",
        close=lambda: None,
    )

    def decide(_request):
        return DecisionResult(
            provider="typesafe",
            model="jev-test",
            answers={
                "goal_satisfied": DecisionAnswer(True, confidence=0.9),
                "material_work_remaining": DecisionAnswer(False, confidence=0.8),
            },
            latency_ms=1.0,
        )

    provider.decide = decide
    monkeypatch.setattr(
        autonomy,
        "get_decision_settings",
        lambda: DecisionSettings(provider="typesafe", source="test"),
    )
    monkeypatch.setattr(autonomy, "create_decision_provider", lambda settings: provider)
    monkeypatch.setattr(
        autonomy, "provider_supports_goal_completion", lambda provider: True
    )
    reviewer_calls = []

    judge = autonomy.SubAgentCompletionJudge(
        reviewer=lambda state: reviewer_calls.append(state) or ("CONTINUE", "")
    )
    outcome = judge.judge(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        raw_output="y",
    )

    assert outcome.complete is True
    assert outcome.source == "decision_provider"
    assert reviewer_calls == []


def test_failed_decision_provider_is_disabled_for_run(monkeypatch):
    calls = {"create": 0, "decide": 0, "close": 0, "review": 0}

    class Provider:
        name = "typesafe"
        model = "jev-test"

        def decide(self, _request):
            calls["decide"] += 1
            raise RuntimeError("offline")

        def close(self):
            calls["close"] += 1

    def create(_settings):
        calls["create"] += 1
        return Provider()

    monkeypatch.setattr(
        autonomy,
        "get_decision_settings",
        lambda: DecisionSettings(provider="typesafe", source="test"),
    )
    monkeypatch.setattr(autonomy, "create_decision_provider", create)
    monkeypatch.setattr(
        autonomy, "provider_supports_goal_completion", lambda provider: True
    )

    def reviewer(_state):
        calls["review"] += 1
        return "CONTINUE", "fallback"

    judge = autonomy.SubAgentCompletionJudge(reviewer=reviewer)
    state = {"goal": "x", "latest_answer": "y", "evidence": []}

    assert judge.judge(state, raw_output="y").source == "llm_reviewer"
    assert judge.judge(state, raw_output="z").source == "llm_reviewer"
    assert calls == {"create": 1, "decide": 1, "close": 1, "review": 2}


def test_followup_prompt_contains_goal_previous_result_and_feedback():
    prompt = autonomy.build_followup_prompt(
        "finish A",
        "partial\n<SUB_AGENT_CONTINUE>",
        "A is not validated",
    )
    assert "finish A" in prompt
    assert "partial" in prompt
    assert "SUB_AGENT_CONTINUE" not in prompt
    assert "A is not validated" in prompt

from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.decision import DecisionAnswer, DecisionResult
from uagent.runtime.goal_completion import (
    ask_goal_completion_decision,
    build_goal_completion_request,
    build_goal_completion_state,
    decision_provider_supports_completion,
)


class _AtomicProvider:
    name = "typesafe"
    model = "jev-latest"

    def __init__(self, *, satisfied=True, remaining=False, error=None):
        self.satisfied = satisfied
        self.remaining = remaining
        self.error = error
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return DecisionResult(
            provider=self.name,
            model=self.model,
            answers={
                "goal_satisfied": DecisionAnswer(
                    self.satisfied,
                    confidence=0.82,
                ),
                "material_work_remaining": DecisionAnswer(
                    self.remaining,
                    confidence=0.79,
                ),
            },
            latency_ms=3.0,
        )


class _LayaProvider:
    name = "laya"
    model = "laya-multilingual"

    def __init__(self, values):
        self.values = list(values)
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        value = self.values[len(self.requests) - 1]
        return DecisionResult(
            provider=self.name,
            model=self.model,
            answers={
                "goal_status": DecisionAnswer(
                    value,
                    confidence=0.7,
                ),
            },
            latency_ms=2.0,
        )


def test_goal_completion_state_isolated_history_needs_no_auto_markers():
    state = build_goal_completion_state(
        [
            {"role": "assistant", "content": "old result"},
            {"role": "user", "content": "Complete A and B"},
            {"role": "assistant", "content": "A complete"},
            {"role": "user", "content": "continue"},
            {"role": "assistant", "content": "B complete"},
        ],
        "Complete A and B",
    )

    assert state == {
        "goal": "Complete A and B",
        "latest_answer": "B complete",
        "evidence": [
            {
                "source": "assistant",
                "status": "reported",
                "summary": "A complete",
            },
        ],
    }


def test_goal_completion_state_masks_and_bounds_tool_evidence():
    state = build_goal_completion_state(
        [
            {"role": "user", "content": "inspect"},
            {
                "role": "tool",
                "name": "demo",
                "tool_call_id": "call-secret",
                "content": '{"ok": true, "result": ' '{"text": "token: secret-value"}}',
            },
            {"role": "assistant", "content": "done"},
        ],
        "inspect",
    )

    assert state["latest_answer"] == "done"
    assert len(state["evidence"]) == 1
    assert state["evidence"][0]["tool"] == "demo"
    assert "call-secret" not in str(state)
    assert "secret-value" not in str(state)
    assert "********" in str(state)


def test_goal_completion_request_supports_custom_site_and_question_id():
    request = build_goal_completion_request(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        site="sub_agent_review",
        choice_question_id="sub_agent_goal_status",
        goal_name="sub-agent goal",
    )

    assert request.metadata["site"] == "sub_agent_review"
    assert request.questions[0].id == "sub_agent_goal_status"
    assert request.questions[0].choices == ("COMPLETE", "CONTINUE")
    assert "sub-agent goal" in request.questions[0].instruction


@pytest.mark.parametrize(
    "satisfied,remaining,expected",
    [
        (True, False, "COMPLETE"),
        (True, True, "CONTINUE"),
        (False, False, "CONTINUE"),
        (False, True, "CONTINUE"),
    ],
)
def test_atomic_goal_completion_normalizes_two_booleans(satisfied, remaining, expected):
    provider = _AtomicProvider(satisfied=satisfied, remaining=remaining)
    attempts = []

    result = ask_goal_completion_decision(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        decision_provider=provider,
        attempt_recorder=attempts.append,
    )

    assert result is not None
    assert result.judgment == expected
    assert result.confidence == 0.79
    assert len(provider.requests) == 1
    assert [question.id for question in provider.requests[0].questions] == [
        "goal_satisfied",
        "material_work_remaining",
    ]
    assert attempts[0]["answer"] == expected


def test_invalid_atomic_answer_requests_fallback():
    provider = _AtomicProvider(satisfied="true", remaining=False)
    logs = []

    result = ask_goal_completion_decision(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        decision_provider=provider,
        log=logs.append,
    )

    assert result is None
    assert "falling back to fallback reviewer" in logs[-1]


def test_laya_requires_reversed_choice_consistency():
    provider = _LayaProvider(["COMPLETE", "COMPLETE"])
    logs = []

    result = ask_goal_completion_decision(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        decision_provider=provider,
        log=logs.append,
    )

    assert result is not None
    assert result.judgment == "COMPLETE"
    assert result.order_consistent is True
    assert len(provider.requests) == 2
    assert provider.requests[0].questions[0].choices == (
        "COMPLETE",
        "CONTINUE",
    )
    assert provider.requests[1].questions[0].choices == (
        "CONTINUE",
        "COMPLETE",
    )
    assert "order_consistent=true" in logs[-1]


def test_laya_order_inconsistency_requests_fallback():
    provider = _LayaProvider(["CONTINUE", "COMPLETE"])
    logs = []

    result = ask_goal_completion_decision(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        decision_provider=provider,
        log=logs.append,
    )

    assert result is None
    assert "order_inconsistent" in logs[-1]


def test_provider_failure_is_secret_masked():
    provider = _AtomicProvider(error=RuntimeError("network failed token: secret-value"))
    logs = []

    result = ask_goal_completion_decision(
        {"goal": "x", "latest_answer": "y", "evidence": []},
        decision_provider=provider,
        log=logs.append,
    )

    assert result is None
    assert "network failed" in logs[-1]
    assert "secret-value" not in logs[-1]
    assert "********" in logs[-1]


@pytest.mark.parametrize(
    "name,kinds,expected",
    [
        ("typesafe", ["boolean"], True),
        ("openrouter", ["noul"], True),
        ("typesafe", ["choice"], False),
        ("laya", ["choice"], True),
        ("laya", ["boolean"], False),
    ],
)
def test_completion_capability_check_uses_provider_question_shape(
    monkeypatch,
    name,
    kinds,
    expected,
):
    import sys

    capability = SimpleNamespace(
        supports=lambda _: True,
        decision=SimpleNamespace(question_kinds=kinds),
    )
    monkeypatch.setitem(
        sys.modules,
        "llmcapa",
        SimpleNamespace(get=lambda *args, **kwargs: capability),
    )

    provider = SimpleNamespace(name=name, model="test")
    assert decision_provider_supports_completion(provider) is expected

from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.decision import DecisionAnswer, DecisionResult
from uagent.decision.goal_completion import (
    GoalCompletionError,
    build_goal_completion_request,
    evaluate_goal_completion,
    provider_supports_goal_completion,
)


class _Provider:
    def __init__(self, name, results):
        self.name = name
        self.model = "test-model"
        self._results = iter(results)
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        result = next(self._results)
        if isinstance(result, BaseException):
            raise result
        return result


def _atomic_result(satisfied, remaining, confidence=0.8):
    return DecisionResult(
        provider="typesafe",
        model="jev-test",
        answers={
            "goal_satisfied": DecisionAnswer(satisfied, confidence=confidence),
            "material_work_remaining": DecisionAnswer(
                remaining,
                confidence=confidence,
            ),
        },
        latency_ms=2.5,
    )


@pytest.mark.parametrize(
    "satisfied,remaining,expected",
    [
        (True, False, "COMPLETE"),
        (True, True, "CONTINUE"),
        (False, False, "CONTINUE"),
        (False, True, "CONTINUE"),
    ],
)
def test_atomic_goal_completion(satisfied, remaining, expected):
    provider = _Provider(
        "typesafe",
        [_atomic_result(satisfied, remaining)],
    )

    evaluation = evaluate_goal_completion(
        provider,
        {"goal": "finish", "latest_answer": "done", "evidence": []},
        site="test_goal_completion",
    )

    assert evaluation.judgment == expected
    assert evaluation.confidence == pytest.approx(0.8)
    assert evaluation.provider == "typesafe"
    assert evaluation.model == "jev-test"
    assert evaluation.latency_ms == pytest.approx(2.5)
    assert len(evaluation.attempts) == 1
    assert provider.requests[0].metadata["site"] == "test_goal_completion"
    assert [question.id for question in provider.requests[0].questions] == [
        "goal_satisfied",
        "material_work_remaining",
    ]


@pytest.mark.parametrize(
    "satisfied,remaining",
    [
        ("true", False),
        (True, None),
    ],
)
def test_atomic_goal_completion_rejects_non_boolean_answers(satisfied, remaining):
    provider = _Provider(
        "typesafe",
        [_atomic_result(satisfied, remaining)],
    )

    with pytest.raises(GoalCompletionError) as exc_info:
        evaluate_goal_completion(provider, {"goal": "finish"})

    error = exc_info.value
    assert error.reason == "provider_or_result_error"
    assert error.failure is not None
    assert error.failure.error_type == "ValueError"
    assert error.attempts == ()


def test_laya_reverses_choice_order_and_requires_consistency():
    primary = DecisionResult(
        provider="laya",
        model="laya-test",
        answers={"status": DecisionAnswer("COMPLETE", confidence=0.7)},
        latency_ms=2.0,
    )
    reversed_result = DecisionResult(
        provider="laya",
        model="laya-test",
        answers={"status": DecisionAnswer("COMPLETE", confidence=0.6)},
        latency_ms=3.0,
    )
    provider = _Provider("laya", [primary, reversed_result])

    evaluation = evaluate_goal_completion(
        provider,
        {"goal": "finish"},
        site="sub_agent_review",
        choice_question_id="status",
        choice_subject="sub-agent goal",
    )

    assert evaluation.judgment == "COMPLETE"
    assert evaluation.order_consistent is True
    assert evaluation.confidence == pytest.approx(0.6)
    assert evaluation.latency_ms == pytest.approx(5.0)
    assert len(evaluation.attempts) == 2
    assert provider.requests[0].questions[0].choices == ("COMPLETE", "CONTINUE")
    assert provider.requests[1].questions[0].choices == ("CONTINUE", "COMPLETE")
    assert provider.requests[0].metadata["site"] == "sub_agent_review"


def test_laya_order_inconsistency_is_rejected_with_attempt_evidence():
    primary = DecisionResult(
        provider="laya",
        model="laya-test",
        answers={"status": DecisionAnswer("CONTINUE")},
        latency_ms=2.0,
    )
    reversed_result = DecisionResult(
        provider="laya",
        model="laya-test",
        answers={"status": DecisionAnswer("COMPLETE")},
        latency_ms=2.0,
    )
    provider = _Provider("laya", [primary, reversed_result])

    with pytest.raises(GoalCompletionError) as exc_info:
        evaluate_goal_completion(
            provider,
            {"goal": "finish"},
            choice_question_id="status",
        )

    error = exc_info.value
    assert error.reason == "order_inconsistent"
    assert [attempt.judgment for attempt in error.attempts] == [
        "CONTINUE",
        "COMPLETE",
    ]
    assert error.failure is None


def test_second_laya_attempt_failure_preserves_primary_attempt():
    primary = DecisionResult(
        provider="laya",
        model="laya-test",
        answers={"status": DecisionAnswer("CONTINUE")},
        latency_ms=2.0,
    )
    provider = _Provider("laya", [primary, RuntimeError("offline")])

    with pytest.raises(GoalCompletionError) as exc_info:
        evaluate_goal_completion(
            provider,
            {"goal": "finish"},
            choice_question_id="status",
        )

    error = exc_info.value
    assert len(error.attempts) == 1
    assert error.attempts[0].judgment == "CONTINUE"
    assert error.failure is not None
    assert error.failure.attempt == "reversed"
    assert error.failure.error_type == "RuntimeError"


def test_build_choice_request_preserves_caller_site_and_subject():
    request = build_goal_completion_request(
        {"goal": "finish"},
        atomic=False,
        site="custom_site",
        choice_question_id="custom_status",
        choice_subject="worker goal",
    )

    question = request.questions[0]
    assert request.metadata["site"] == "custom_site"
    assert question.id == "custom_status"
    assert "worker goal" in question.instruction


@pytest.mark.parametrize(
    "name,kinds,expected",
    [
        ("typesafe", ["boolean"], True),
        ("openrouter", ["noul"], True),
        ("openai", ["predicate"], True),
        ("typesafe", ["choice"], False),
        ("laya", ["choice"], True),
        ("laya", ["boolean"], False),
    ],
)
def test_goal_completion_capability_check(monkeypatch, name, kinds, expected):
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

    assert provider_supports_goal_completion(provider) is expected

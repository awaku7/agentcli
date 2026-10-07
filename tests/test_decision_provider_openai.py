from __future__ import annotations

import httpx
import pytest

from uagent.decision import (
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionSettings,
    create_decision_provider,
)
from uagent.decision.goal_completion import evaluate_goal_completion
from uagent.decision.openai import (
    OpenAIDecisionConfig,
    OpenAIDecisionConfigurationError,
    OpenAIDecisionError,
    OpenAIDecisionProvider,
    _decisions_url,
)


class FakeResponse:
    def __init__(self, payload, *, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeClient:
    def __init__(self, response=None, *, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.closed = False

    def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": dict(headers), "json": json})
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _settings():
    return DecisionSettings(provider="openai", source="env")


def _environ(**overrides):
    values = {
        "UAGENT_DECISION_OPENAI_API_KEY": "secret-key",
        "UAGENT_DECISION_OPENAI_DEPNAME": "gpt-6-luna",
        "UAGENT_DECISION_OPENAI_BASE_URL": "https://api.openai.com/v1",
    }
    values.update(overrides)
    return values


def test_openai_config_defaults_and_secret_is_not_repr():
    config = OpenAIDecisionConfig.from_environment(
        {"UAGENT_DECISION_OPENAI_API_KEY": "top-secret"}
    )

    assert config.model == "gpt-6-luna"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.api_key == "top-secret"
    assert "top-secret" not in repr(config)


@pytest.mark.parametrize(
    ("environ", "expected_key"),
    [
        ({"UAGENT_DECISION_OPENAI_API_KEY": "decision-key"}, "decision-key"),
        ({"UAGENT_OPENAI_API_KEY": "uag-key"}, "uag-key"),
        ({"OPENAI_API_KEY": "standard-key"}, "standard-key"),
    ],
)
def test_openai_api_key_fallbacks(environ, expected_key):
    assert OpenAIDecisionConfig.from_environment(environ).api_key == expected_key


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://api.openai.com/v1", "https://api.openai.com/v1/decisions"),
        ("https://api.openai.com/v1/", "https://api.openai.com/v1/decisions"),
        (
            "https://api.openai.com/v1/decisions",
            "https://api.openai.com/v1/decisions",
        ),
        ("https://example.test", "https://example.test/v1/decisions"),
    ],
)
def test_decisions_url(base_url, expected):
    assert _decisions_url(base_url) == expected


def test_openai_requires_api_key_only_when_adapter_is_created():
    with pytest.raises(OpenAIDecisionConfigurationError, match="OPENAI_API_KEY"):
        OpenAIDecisionProvider(
            settings=_settings(), environ={}, client=FakeClient()
        )


def test_registry_creates_openai_adapter():
    provider = create_decision_provider(
        _settings(), environ=_environ(), client=FakeClient()
    )

    assert isinstance(provider, OpenAIDecisionProvider)
    assert provider.name == "openai"
    assert provider.model == "gpt-6-luna"


def test_openai_decisions_adapter_translates_all_question_kinds():
    client = FakeClient(
        FakeResponse(
            {
                "model": "gpt-6-luna",
                "answers": [
                    {
                        "type": "predicate",
                        "name": "ready",
                        "probability": 0.91,
                    },
                    {
                        "type": "choice",
                        "name": "route",
                        "choice": "CONTINUE",
                        "confidence": 0.86,
                        "probabilities": [
                            {"value": "COMPLETE", "probability": 0.14},
                            {"value": "CONTINUE", "probability": 0.86},
                        ],
                    },
                    {
                        "type": "score",
                        "name": "risk",
                        "score": 1.1,
                        "confidence": 0.55,
                        "probabilities": [
                            {"value": 0, "label": "low", "probability": 0.1},
                            {"value": 1, "label": "medium", "probability": 0.7},
                            {"value": 2, "label": "high", "probability": 0.2},
                        ],
                    },
                ],
            }
        )
    )
    provider = OpenAIDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )
    request = DecisionRequest(
        state={"goal": "finish", "status": "done"},
        questions=(
            DecisionQuestion(
                id="ready",
                kind=DecisionKind.BOOLEAN,
                instruction="Is the work ready?",
                metadata={"criteria": {"true": "ready", "false": "not ready"}},
            ),
            DecisionQuestion(
                id="route",
                kind=DecisionKind.CHOICE,
                instruction="Should the task stop or continue?",
                choices=("COMPLETE", "CONTINUE"),
                metadata={"criteria": {"COMPLETE": "finished", "CONTINUE": "more work"}},
            ),
            DecisionQuestion(
                id="risk",
                kind=DecisionKind.SCORE,
                instruction="Rate remaining risk.",
                choices=("low", "medium", "high"),
                metadata={"criteria": ["low risk", "medium risk", "high risk"]},
            ),
        ),
    )

    result = provider.decide(request)

    assert client.calls[0]["url"] == "https://api.openai.com/v1/decisions"
    assert client.calls[0]["headers"]["Authorization"] == "Bearer secret-key"
    assert client.calls[0]["json"] == {
        "model": "gpt-6-luna",
        "input": '{"goal":"finish","status":"done"}',
        "questions": [
            {
                "name": "ready",
                "type": "predicate",
                "instructions": (
                    "Is the work ready?\n\nTRUE means: ready FALSE means: not ready"
                ),
            },
            {
                "name": "route",
                "type": "choice",
                "instructions": "Should the task stop or continue?",
                "choices": [
                    {"value": "COMPLETE", "description": "finished"},
                    {"value": "CONTINUE", "description": "more work"},
                ],
            },
            {
                "name": "risk",
                "type": "score",
                "instructions": "Rate remaining risk.",
                "levels": [
                    {"label": "low", "description": "low risk"},
                    {"label": "medium", "description": "medium risk"},
                    {"label": "high", "description": "high risk"},
                ],
            },
        ],
    }
    assert result.provider == "openai"
    assert result.answers["ready"].value is True
    assert result.answers["ready"].confidence == pytest.approx(0.91)
    assert result.answers["route"].value == "CONTINUE"
    assert result.answers["route"].confidence == pytest.approx(0.86)
    assert result.answers["route"].metadata["probabilities"]["COMPLETE"] == pytest.approx(0.14)
    assert result.answers["risk"].value == pytest.approx(1.1)
    assert result.answers["risk"].metadata["probabilities"]["1"] == pytest.approx(0.7)


def test_openai_predicates_integrate_with_goal_completion_evaluation():
    client = FakeClient(
        FakeResponse(
            {
                "answers": [
                    {
                        "type": "predicate",
                        "name": "goal_satisfied",
                        "probability": 0.93,
                    },
                    {
                        "type": "predicate",
                        "name": "material_work_remaining",
                        "probability": 0.08,
                    },
                ]
            }
        )
    )
    provider = OpenAIDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )

    evaluation = evaluate_goal_completion(
        provider,
        {"goal": "Finish the task", "latest_answer": "Done", "evidence": []},
    )

    assert evaluation.judgment == "COMPLETE"
    assert evaluation.provider == "openai"
    assert [
        question["type"] for question in client.calls[0]["json"]["questions"]
    ] == ["predicate", "predicate"]


def test_openai_rejects_wrong_answer_types_and_probability_ranges():
    provider = OpenAIDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {
                    "answers": [
                        {"type": "predicate", "name": "flag", "probability": 1.1}
                    ]
                }
            )
        ),
    )
    request = DecisionRequest(
        state="context",
        questions=(DecisionQuestion("flag", "boolean", "Is it true?"),),
    )

    with pytest.raises(OpenAIDecisionError, match=r"outside \[0, 1\]"):
        provider.decide(request)


def test_openai_rejects_duplicate_question_ids_and_missing_answers():
    provider = OpenAIDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(FakeResponse({"answers": []})),
    )
    question = DecisionQuestion("flag", "boolean", "Is it true?")
    with pytest.raises(OpenAIDecisionError, match="duplicate question ids"):
        provider.decide(DecisionRequest("context", (question, question)))
    with pytest.raises(OpenAIDecisionError, match="missing answer 'flag'"):
        provider.decide(DecisionRequest("context", (question,)))


def test_openai_http_errors_are_redacted_and_client_lifecycle_is_safe():
    client = FakeClient(error=httpx.ConnectError("network failure"))
    provider = OpenAIDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )
    with pytest.raises(OpenAIDecisionError, match="ConnectError"):
        provider.decide(
            DecisionRequest(
                "context", (DecisionQuestion("flag", "boolean", "Is it true?"),)
            )
        )
    provider.close()
    assert not client.closed  # Injected clients remain caller-owned.


def test_openai_error_response_redacts_api_key():
    class ErrorResponse(FakeResponse):
        text = "request failed using secret-key"

    provider = OpenAIDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(ErrorResponse({}, status_code=401)),
    )
    with pytest.raises(OpenAIDecisionError) as exc_info:
        provider.decide(
            DecisionRequest(
                "context", (DecisionQuestion("flag", "boolean", "Is it true?"),)
            )
        )
    assert "secret-key" not in str(exc_info.value)

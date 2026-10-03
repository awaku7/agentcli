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
from uagent.decision.openrouter import (
    OpenRouterDecisionConfig,
    OpenRouterDecisionConfigurationError,
    OpenRouterDecisionError,
    OpenRouterDecisionProvider,
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
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "json": json,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _settings():
    return DecisionSettings(provider="openrouter", source="env")


def _environ(**overrides):
    values = {
        "UAGENT_DECISION_OPENROUTER_API_KEY": "secret-key",
        "UAGENT_DECISION_OPENROUTER_DEPNAME": "~typesafe/jev-latest",
        "UAGENT_DECISION_OPENROUTER_BASE_URL": "https://openrouter.ai/api",
    }
    values.update(overrides)
    return values


def test_openrouter_config_defaults_and_secret_is_not_repr():
    config = OpenRouterDecisionConfig.from_environment(
        {"UAGENT_DECISION_OPENROUTER_API_KEY": "top-secret"}
    )

    assert config.model == "~typesafe/jev-latest"
    assert config.base_url == "https://openrouter.ai/api"
    assert config.api_key == "top-secret"
    assert "top-secret" not in repr(config)


@pytest.mark.parametrize(
    ("environ", "expected_key"),
    [
        ({"UAGENT_DECISION_OPENROUTER_API_KEY": "decision-key"}, "decision-key"),
        ({"UAGENT_OPENROUTER_API_KEY": "uag-key"}, "uag-key"),
        ({"OPENROUTER_API_KEY": "standard-key"}, "standard-key"),
    ],
)
def test_openrouter_api_key_fallbacks(environ, expected_key):
    config = OpenRouterDecisionConfig.from_environment(environ)

    assert config.api_key == expected_key


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (
            "https://openrouter.ai/api",
            "https://openrouter.ai/api/alpha/decisions",
        ),
        (
            "https://openrouter.ai/api/",
            "https://openrouter.ai/api/alpha/decisions",
        ),
        (
            "https://openrouter.ai/api/v1",
            "https://openrouter.ai/api/alpha/decisions",
        ),
        (
            "https://example.test/api/alpha",
            "https://example.test/api/alpha/decisions",
        ),
        (
            "https://example.test/api/alpha/decisions",
            "https://example.test/api/alpha/decisions",
        ),
    ],
)
def test_decisions_url(base_url, expected):
    assert _decisions_url(base_url) == expected


def test_openrouter_requires_api_key_only_when_adapter_is_created():
    with pytest.raises(
        OpenRouterDecisionConfigurationError,
        match="OPENROUTER_API_KEY",
    ):
        OpenRouterDecisionProvider(
            settings=_settings(),
            environ={},
            client=FakeClient(),
        )


def test_registry_creates_openrouter_adapter():
    provider = create_decision_provider(
        _settings(),
        environ=_environ(),
        client=FakeClient(),
    )

    assert isinstance(provider, OpenRouterDecisionProvider)
    assert provider.name == "openrouter"


def test_openrouter_adapter_translates_all_common_question_kinds():
    response = FakeResponse(
        {
            "id": "gen-dec-test",
            "provider": "TypeSafe",
            "model": "typesafe/jev-1.13-20260917",
            "answers": {
                "is_ready": {
                    "type": "noul",
                    "noul": 0.2,
                },
                "route": {
                    "type": "choice",
                    "choice": "CONTINUE",
                    "confidence": 0.84,
                    "probabilities": {
                        "COMPLETE": 0.16,
                        "CONTINUE": 0.84,
                    },
                },
                "risk": {
                    "type": "score",
                    "score": 1.4,
                    "confidence": 0.72,
                    "legend": {
                        "0": "low",
                        "1": "medium",
                        "2": "high",
                    },
                    "probabilities": {
                        "0": 0.1,
                        "1": 0.4,
                        "2": 0.5,
                    },
                },
            },
            "usage": {
                "input_tokens": 123,
                "output_tokens": 9,
                "cost": 0.00001,
            },
        }
    )
    client = FakeClient(response)
    provider = OpenRouterDecisionProvider(
        settings=_settings(),
        environ=_environ(
            UAGENT_DECISION_OPENROUTER_DEPNAME="typesafe/jev-1.13",
            UAGENT_DECISION_OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        ),
        client=client,
    )
    request = DecisionRequest(
        state={"goal": "Finish the task", "round": 2},
        questions=(
            DecisionQuestion(
                id="is_ready",
                kind=DecisionKind.BOOLEAN,
                instruction="Is the result fully ready?",
                metadata={
                    "criteria": {
                        "true": "No material work remains.",
                        "false": "Material work remains.",
                    }
                },
            ),
            DecisionQuestion(
                id="route",
                kind=DecisionKind.CHOICE,
                instruction="Should the task stop or continue?",
                choices=("COMPLETE", "CONTINUE"),
                metadata={
                    "criteria": {
                        "COMPLETE": "All required work is finished.",
                        "CONTINUE": "Additional work is required.",
                    }
                },
            ),
            DecisionQuestion(
                id="risk",
                kind=DecisionKind.SCORE,
                instruction="Rate remaining risk.",
                choices=("low", "medium", "high"),
            ),
        ),
    )

    result = provider.decide(request)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://openrouter.ai/api/alpha/decisions"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["json"]["model"] == "typesafe/jev-1.13"
    assert call["json"]["state"] == request.state
    assert call["json"]["questions"]["is_ready"]["type"] == "noul"
    assert call["json"]["questions"]["route"]["type"] == "choice"
    assert call["json"]["questions"]["risk"]["type"] == "score"

    assert result.provider == "openrouter"
    assert result.model == "typesafe/jev-1.13-20260917"
    assert result.answers["is_ready"].value is False
    assert result.answers["is_ready"].calibrated is True
    assert result.answers["route"].value == "CONTINUE"
    assert result.answers["route"].confidence == pytest.approx(0.84)
    assert result.answers["risk"].value == pytest.approx(1.4)
    assert result.raw["provider"] == "TypeSafe"


def test_openrouter_http_failure_is_not_a_decision():
    provider = OpenRouterDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            error=httpx.ConnectError(
                "boom",
                request=httpx.Request(
                    "POST",
                    "https://openrouter.ai/api/alpha/decisions",
                ),
            )
        ),
    )

    with pytest.raises(OpenRouterDecisionError, match="ConnectError"):
        provider.decide(
            DecisionRequest(
                state="state",
                questions=(
                    DecisionQuestion(
                        id="route",
                        kind="choice",
                        instruction="Choose.",
                        choices=("A", "B"),
                    ),
                ),
            )
        )


def test_openrouter_rejects_invalid_response_shape():
    provider = OpenRouterDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(FakeResponse({"model": "typesafe/jev-1.13"})),
    )

    with pytest.raises(OpenRouterDecisionError, match="answers object"):
        provider.decide(
            DecisionRequest(
                state="state",
                questions=(
                    DecisionQuestion(
                        id="route",
                        kind="choice",
                        instruction="Choose.",
                        choices=("A", "B"),
                    ),
                ),
            )
        )


def test_injected_client_is_not_closed():
    client = FakeClient()
    provider = OpenRouterDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=client,
    )

    provider.close()
    provider.close()

    assert client.closed is False


def test_openrouter_choice_common_confidence_uses_selected_probability():
    provider = OpenRouterDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {
                    "model": "typesafe/jev-1.13",
                    "answers": {
                        "route": {
                            "type": "choice",
                            "choice": "A",
                            "confidence": 0.52,
                            "probabilities": {"A": 0.79, "B": 0.21},
                        }
                    },
                }
            )
        ),
    )

    result = provider.decide(
        DecisionRequest(
            state="state",
            questions=(
                DecisionQuestion(
                    id="route",
                    kind="choice",
                    instruction="Choose.",
                    choices=("A", "B"),
                ),
            ),
        )
    )

    answer = result.answers["route"]
    assert answer.confidence == pytest.approx(0.79)
    assert answer.metadata["provider_confidence"] == pytest.approx(0.52)


def test_openrouter_http_error_detail_is_secret_masked():
    provider = OpenRouterDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {"error": {"message": "Invalid API key secret-key"}},
                status_code=401,
            )
        ),
    )

    with pytest.raises(OpenRouterDecisionError) as exc_info:
        provider.decide(
            DecisionRequest(
                state="state",
                questions=(
                    DecisionQuestion(
                        id="route",
                        kind="choice",
                        instruction="Choose.",
                        choices=("A", "B"),
                    ),
                ),
            )
        )

    message = str(exc_info.value)
    assert "HTTP 401" in message
    assert "secret-key" not in message
    assert "********" in message


def test_auto_completion_sends_two_noul_questions_in_one_call():
    from uagent.util_cmd_auto import _build_auto_pilot_decision_request

    client = FakeClient(
        FakeResponse(
            {
                "answers": {
                    "goal_satisfied": {"type": "noul", "noul": 0.9},
                    "material_work_remaining": {"type": "noul", "noul": 0.1},
                }
            }
        )
    )
    provider = OpenRouterDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )
    request = _build_auto_pilot_decision_request(
        {"goal": "weather", "latest_answer": "sunny", "evidence": []}, atomic=True
    )
    result = provider.decide(request)
    assert len(client.calls) == 1
    questions = client.calls[0]["json"]["questions"]
    assert set(questions) == {"goal_satisfied", "material_work_remaining"}
    assert all(question["type"] == "noul" for question in questions.values())
    assert result.answers["goal_satisfied"].value is True
    assert result.answers["material_work_remaining"].value is False

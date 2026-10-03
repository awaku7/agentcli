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
from uagent.decision.typesafe import (
    TypeSafeDecisionConfigurationError,
    TypeSafeDecisionError,
    TypeSafeDecisionProvider,
    TypeSafeDecisionConfig,
    _system_one_url,
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
    return DecisionSettings(provider="typesafe", source="env")


def _environ(**overrides):
    values = {
        "UAGENT_DECISION_TYPESAFE_API_KEY": "secret-key",
        "UAGENT_DECISION_TYPESAFE_DEPNAME": "jev-latest",
        "UAGENT_DECISION_TYPESAFE_BASE_URL": "https://api.typesafe.ai",
    }
    values.update(overrides)
    return values


def test_typesafe_config_defaults_and_secret_is_not_repr():
    config = TypeSafeDecisionConfig.from_environment(
        {"UAGENT_DECISION_TYPESAFE_API_KEY": "top-secret"}
    )

    assert config.model == "jev-latest"
    assert config.base_url == "https://api.typesafe.ai"
    assert config.api_key == "top-secret"
    assert "top-secret" not in repr(config)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://api.typesafe.ai", "https://api.typesafe.ai/v1/systemone"),
        ("https://api.typesafe.ai/", "https://api.typesafe.ai/v1/systemone"),
        ("https://example.test/v1", "https://example.test/v1/systemone"),
        (
            "https://example.test/v1/systemone",
            "https://example.test/v1/systemone",
        ),
    ],
)
def test_system_one_url(base_url, expected):
    assert _system_one_url(base_url) == expected


def test_typesafe_requires_api_key_only_when_adapter_is_created():
    with pytest.raises(
        TypeSafeDecisionConfigurationError,
        match="UAGENT_DECISION_TYPESAFE_API_KEY",
    ):
        TypeSafeDecisionProvider(
            settings=_settings(),
            environ={},
            client=FakeClient(),
        )


def test_typesafe_adapter_translates_all_common_question_kinds():
    response = FakeResponse(
        {
            "model": "jev-1.13.0",
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
            },
        }
    )
    client = FakeClient(response)
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(
            UAGENT_DECISION_TYPESAFE_DEPNAME="jev-1.13.0",
            UAGENT_DECISION_TYPESAFE_BASE_URL="https://api.typesafe.ai/v1",
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
                instruction="Rate the remaining risk.",
                choices=("low", "medium", "high"),
            ),
        ),
    )

    result = provider.decide(request)

    assert provider.name == "typesafe"
    assert provider.model == "jev-1.13.0"
    assert result.provider == "typesafe"
    assert result.model == "jev-1.13.0"
    assert result.skipped is False
    assert result.latency_ms >= 0.0

    assert result.answers["is_ready"].value is False
    assert result.answers["is_ready"].confidence == pytest.approx(0.8)
    assert result.answers["is_ready"].calibrated is True
    assert result.answers["is_ready"].metadata["probability_true"] == pytest.approx(0.2)

    assert result.answers["route"].value == "CONTINUE"
    assert result.answers["route"].confidence == pytest.approx(0.84)
    assert result.answers["route"].metadata["probabilities"]["COMPLETE"] == 0.16

    assert result.answers["risk"].value == pytest.approx(1.4)
    assert result.answers["risk"].confidence == pytest.approx(0.72)
    assert result.answers["risk"].metadata["legend"]["2"] == "high"

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://api.typesafe.ai/v1/systemone"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["json"]["model"] == "jev-1.13.0"
    assert call["json"]["state"] == request.state
    assert call["json"]["questions"]["is_ready"] == {
        "type": "noul",
        "instructions": "Is the result fully ready?",
        "criteria": {
            "true": "No material work remains.",
            "false": "Material work remains.",
        },
    }
    assert call["json"]["questions"]["route"] == {
        "type": "choice",
        "instructions": "Should the task stop or continue?",
        "criteria": {
            "COMPLETE": "All required work is finished.",
            "CONTINUE": "Additional work is required.",
        },
    }
    assert call["json"]["questions"]["risk"] == {
        "type": "score",
        "instructions": "Rate the remaining risk.",
        "criteria": ["low", "medium", "high"],
    }


def test_registry_creates_typesafe_adapter_lazily():
    client = FakeClient(FakeResponse({"model": "jev-latest", "answers": {}}))

    provider = create_decision_provider(
        _settings(),
        environ=_environ(),
        client=client,
    )

    assert isinstance(provider, TypeSafeDecisionProvider)
    assert provider.name == "typesafe"


def test_typesafe_http_status_failure_is_not_a_decision():
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(FakeResponse({}, status_code=503)),
    )
    request = DecisionRequest(
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

    with pytest.raises(TypeSafeDecisionError, match="HTTP 503"):
        provider.decide(request)


def test_typesafe_transport_failure_is_not_a_decision():
    request = httpx.Request("POST", "https://api.typesafe.ai/v1/systemone")
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(error=httpx.ConnectError("offline", request=request)),
    )

    with pytest.raises(TypeSafeDecisionError, match="ConnectError"):
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


def test_typesafe_missing_answer_is_rejected():
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {
                    "model": "jev-latest",
                    "answers": {},
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 0,
                    },
                }
            )
        ),
    )

    with pytest.raises(TypeSafeDecisionError, match="missing answer 'route'"):
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


def test_typesafe_mismatched_answer_type_is_rejected():
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {
                    "model": "jev-latest",
                    "answers": {
                        "route": {
                            "type": "noul",
                            "noul": 0.9,
                        }
                    },
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 1,
                    },
                }
            )
        ),
    )

    with pytest.raises(TypeSafeDecisionError, match="expected 'choice'"):
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


def test_typesafe_validates_common_question_shapes_before_http():
    client = FakeClient(FakeResponse({}))
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=client,
    )

    with pytest.raises(TypeSafeDecisionError, match="at least one choice"):
        provider.decide(
            DecisionRequest(
                state="state",
                questions=(
                    DecisionQuestion(
                        id="route",
                        kind="choice",
                        instruction="Choose.",
                    ),
                ),
            )
        )

    assert client.calls == []


def test_injected_client_is_not_closed_by_provider():
    client = FakeClient(FakeResponse({}))
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=client,
    )

    provider.close()
    provider.close()

    assert client.closed is False


def test_typesafe_rejects_duplicate_question_ids_before_http():
    client = FakeClient(FakeResponse({}))
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=client,
    )
    duplicated = DecisionQuestion(
        id="same",
        kind="choice",
        instruction="Choose.",
        choices=("A", "B"),
    )

    with pytest.raises(TypeSafeDecisionError, match="duplicate question ids"):
        provider.decide(
            DecisionRequest(
                state="state",
                questions=(duplicated, duplicated),
            )
        )

    assert client.calls == []


def test_typesafe_unrecognized_choice_is_rejected():
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {
                    "model": "jev-latest",
                    "answers": {
                        "route": {
                            "type": "choice",
                            "choice": "C",
                            "confidence": 0.8,
                            "probabilities": {
                                "A": 0.1,
                                "B": 0.1,
                                "C": 0.8,
                            },
                        }
                    },
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 1,
                    },
                }
            )
        ),
    )

    with pytest.raises(TypeSafeDecisionError, match="unrecognized choice 'C'"):
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


def test_typesafe_choice_requires_probabilities():
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {
                    "model": "jev-latest",
                    "answers": {
                        "route": {
                            "type": "choice",
                            "choice": "A",
                            "confidence": 0.8,
                        }
                    },
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 1,
                    },
                }
            )
        ),
    )

    with pytest.raises(TypeSafeDecisionError, match="missing probabilities"):
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


def test_typesafe_choice_common_confidence_uses_selected_probability():
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {
                    "model": "jev-latest",
                    "answers": {
                        "route": {
                            "type": "choice",
                            "choice": "A",
                            "confidence": 0.55,
                            "probabilities": {"A": 0.8, "B": 0.2},
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
    assert answer.confidence == pytest.approx(0.8)
    assert answer.calibrated is True
    assert answer.metadata["provider_confidence"] == pytest.approx(0.55)


def test_typesafe_http_error_detail_is_bounded_and_secret_masked():
    provider = TypeSafeDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            FakeResponse(
                {"detail": "invalid model token: secret-value"},
                status_code=422,
            )
        ),
    )

    with pytest.raises(TypeSafeDecisionError) as exc_info:
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
    assert "HTTP 422" in message
    assert "invalid model" in message
    assert "secret-value" not in message
    assert "********" in message

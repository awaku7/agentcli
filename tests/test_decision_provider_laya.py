from __future__ import annotations

import types

import pytest

from uagent.decision import (
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionSettings,
    create_decision_provider,
)
from uagent.decision.laya import (
    LayaDecisionConfig,
    LayaDecisionError,
    LayaDecisionProvider,
    LayaDecisionUnavailableError,
)


class FakeRouter:
    def __init__(self, response=None, *, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.closed = False

    def predict(self, state, questions, *, model=None):
        self.calls.append(
            {
                "state": state,
                "questions": questions,
                "model": model,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _settings():
    return DecisionSettings(provider="laya", source="env")


def _environ(**overrides):
    values = {
        "UAGENT_DECISION_LAYA_DEPNAME": "laya-multilingual",
        "UAGENT_DECISION_LAYA_DEVICE": "auto",
    }
    values.update(overrides)
    return values


def test_laya_config_defaults():
    config = LayaDecisionConfig.from_environment({})

    assert config.model == "laya-multilingual"
    assert config.device == "auto"


def test_laya_runtime_import_is_deferred_until_first_decide():
    imports = []

    def fail_if_called(name):
        imports.append(name)
        raise AssertionError("Laya must not be imported at provider construction time.")

    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        module_loader=fail_if_called,
    )

    assert provider.name == "laya"
    assert provider.model == "laya-multilingual"
    assert provider.device == "auto"
    assert imports == []


def test_registry_creates_laya_adapter_without_importing_laya_runtime():
    imports = []

    def fail_if_called(name):
        imports.append(name)
        raise AssertionError("Laya runtime import must remain deferred.")

    provider = create_decision_provider(
        _settings(),
        environ=_environ(),
        module_loader=fail_if_called,
    )

    assert isinstance(provider, LayaDecisionProvider)
    assert imports == []


def test_laya_first_decide_builds_lazy_router_without_preload():
    constructed = []

    class Router:
        def __init__(self, **kwargs):
            constructed.append(dict(kwargs))

        def predict(self, state, questions, *, model=None):
            return {
                "model": "laya-rl-agent",
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": "CONTINUE",
                        "probabilities": {
                            "COMPLETE": 0.2,
                            "CONTINUE": 0.8,
                        },
                        "confidence": 0.55,
                        "answer_confidence": 0.8,
                        "action": {
                            "act_probability": 1.0,
                        },
                    }
                },
                "routing": {
                    "model": "multilingual",
                },
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 0,
                },
            }

    loaded = []

    def loader(name):
        loaded.append(name)
        return types.SimpleNamespace(Router=Router)

    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        module_loader=loader,
    )
    request = DecisionRequest(
        state={"goal": "finish"},
        questions=(
            DecisionQuestion(
                id="route",
                kind="choice",
                instruction="Choose.",
                choices=("COMPLETE", "CONTINUE"),
            ),
        ),
    )

    result = provider.decide(request)

    assert loaded == ["laya"]
    assert constructed == [
        {
            "device": None,
            "max_loaded": 1,
            "preload": False,
        }
    ]
    assert result.provider == "laya"
    assert result.model == "laya-multilingual"
    assert result.answers["route"].value == "CONTINUE"
    assert result.answers["route"].confidence == pytest.approx(0.8)
    assert result.answers["route"].calibrated is False
    assert result.answers["route"].metadata["entropy_confidence"] == pytest.approx(0.55)
    assert result.answers["route"].metadata["act_probability"] == pytest.approx(1.0)


def test_laya_device_is_forwarded_when_not_auto():
    seen = []

    class Router:
        def __init__(self, **kwargs):
            seen.append(dict(kwargs))

        def predict(self, state, questions, *, model=None):
            return {
                "answers": {
                    "flag": {
                        "type": "noul",
                        "noul": 0.9,
                        "confidence": 0.7,
                        "answer_confidence": 0.9,
                    }
                },
                "routing": {
                    "model": "english",
                },
            }

    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(UAGENT_DECISION_LAYA_DEVICE="cuda"),
        module_loader=lambda _name: types.SimpleNamespace(Router=Router),
    )

    provider.decide(
        DecisionRequest(
            state="state",
            questions=(
                DecisionQuestion(
                    id="flag",
                    kind="boolean",
                    instruction="True?",
                ),
            ),
        )
    )

    assert seen[0]["device"] == "cuda"


def test_laya_translates_all_common_question_kinds():
    router = FakeRouter(
        {
            "model": "laya-rl-agent",
            "answers": {
                "ready": {
                    "type": "noul",
                    "noul": 0.2,
                    "confidence": 0.51,
                    "answer_confidence": 0.8,
                    "action": {
                        "act_probability": 0.95,
                    },
                },
                "route": {
                    "type": "choice",
                    "choice": "CONTINUE",
                    "probabilities": {
                        "COMPLETE": 0.16,
                        "CONTINUE": 0.84,
                    },
                    "confidence": 0.44,
                    "answer_confidence": 0.84,
                },
                "risk": {
                    "type": "score",
                    "score": 1.4,
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
                    "confidence": 0.31,
                    "answer_confidence": 0.5,
                },
            },
            "routing": {
                "model": "multilingual",
            },
            "usage": {
                "input_tokens": 42,
                "output_tokens": 0,
            },
        }
    )
    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        router=router,
    )
    request = DecisionRequest(
        state={"goal": "Finish the task", "round": 2},
        questions=(
            DecisionQuestion(
                id="ready",
                kind=DecisionKind.BOOLEAN,
                instruction="Is the task fully ready?",
                metadata={
                    "criteria": {
                        "true": "No work remains.",
                        "false": "Work remains.",
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

    assert result.model == "laya-multilingual"
    assert result.latency_ms >= 0.0

    assert result.answers["ready"].value is False
    assert result.answers["ready"].confidence == pytest.approx(0.8)
    assert result.answers["ready"].calibrated is False
    assert result.answers["ready"].metadata["probability_true"] == pytest.approx(0.2)
    assert result.answers["ready"].metadata["act_probability"] == pytest.approx(0.95)

    assert result.answers["route"].value == "CONTINUE"
    assert result.answers["route"].confidence == pytest.approx(0.84)
    assert result.answers["route"].calibrated is False
    assert result.answers["route"].metadata["probabilities"]["COMPLETE"] == 0.16

    assert result.answers["risk"].value == pytest.approx(1.4)
    assert result.answers["risk"].confidence == pytest.approx(0.5)
    assert result.answers["risk"].calibrated is False
    assert result.answers["risk"].metadata["legend"]["2"] == "high"

    assert len(router.calls) == 1
    call = router.calls[0]
    assert call["model"] == "laya-multilingual"
    assert call["state"] == request.state
    assert call["questions"]["ready"] == {
        "instructions": "Is the task fully ready?",
        "type": "noul",
        "criteria": {
            "true": "No work remains.",
            "false": "Work remains.",
        },
    }
    assert call["questions"]["route"] == {
        "instructions": "Should the task stop or continue?",
        "type": "choice",
        "criteria": {
            "COMPLETE": "All required work is finished.",
            "CONTINUE": "Additional work is required.",
        },
    }
    assert call["questions"]["risk"] == {
        "instructions": "Rate remaining risk.",
        "type": "score",
        "criteria": ["low", "medium", "high"],
    }


def test_laya_missing_optional_dependency_is_actionable():
    def missing(name):
        raise ModuleNotFoundError(name=name)

    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        module_loader=missing,
    )

    with pytest.raises(
        LayaDecisionUnavailableError,
        match=r"uag\[decision-laya\]",
    ):
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


def test_laya_provider_failure_is_not_a_decision():
    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        router=FakeRouter(error=RuntimeError("boom")),
    )

    with pytest.raises(LayaDecisionError, match="RuntimeError"):
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


def test_laya_rejects_unrecognized_choice():
    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        router=FakeRouter(
            {
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": "C",
                        "probabilities": {
                            "A": 0.1,
                            "B": 0.1,
                            "C": 0.8,
                        },
                        "confidence": 0.4,
                        "answer_confidence": 0.8,
                    }
                },
                "routing": {
                    "model": "multilingual",
                },
            }
        ),
    )

    with pytest.raises(LayaDecisionError, match="unrecognized choice 'C'"):
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


def test_laya_rejects_missing_answer_confidence():
    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        router=FakeRouter(
            {
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": "A",
                        "probabilities": {
                            "A": 0.8,
                            "B": 0.2,
                        },
                        "confidence": 0.4,
                    }
                },
                "routing": {
                    "model": "multilingual",
                },
            }
        ),
    )

    with pytest.raises(LayaDecisionError, match="answer_confidence"):
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


def test_laya_rejects_duplicate_question_ids_before_inference():
    router = FakeRouter({})
    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        router=router,
    )
    duplicated = DecisionQuestion(
        id="same",
        kind="choice",
        instruction="Choose.",
        choices=("A", "B"),
    )

    with pytest.raises(LayaDecisionError, match="duplicate question ids"):
        provider.decide(
            DecisionRequest(
                state="state",
                questions=(duplicated, duplicated),
            )
        )

    assert router.calls == []


def test_injected_router_is_not_closed_by_provider():
    router = FakeRouter({})
    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        router=router,
    )

    provider.close()
    provider.close()

    assert router.closed is False


def test_owned_router_is_closed_when_supported():
    routers = []

    class Router(FakeRouter):
        def __init__(self, **_kwargs):
            super().__init__({})
            routers.append(self)

    provider = LayaDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        module_loader=lambda _name: types.SimpleNamespace(Router=Router),
    )
    provider._get_router()
    provider.close()
    provider.close()

    assert routers[0].closed is True

from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.decision.capabilities import validate_model_decision_request
from uagent.decision.models import DecisionQuestion, DecisionRequest


class CapabilityError(RuntimeError):
    pass


def _request(kind: str = "boolean") -> DecisionRequest:
    choices = ("A", "B") if kind == "choice" else ()
    return DecisionRequest(
        state="state",
        questions=(
            DecisionQuestion(
                id="q1",
                kind=kind,
                instruction="Evaluate the state.",
                choices=choices,
            ),
        ),
    )


def _decision(
    *,
    supported: bool | None = True,
    question_kinds: tuple[str, ...] = ("predicate", "choice", "score"),
    answer_fields: tuple[str, ...] = ("probability", "choice", "score"),
    calibrated_confidence: bool | None = None,
):
    return SimpleNamespace(
        decision=supported,
        question_kinds=question_kinds,
        answer_fields=answer_fields,
        calibrated_confidence=calibrated_confidence,
    )


def test_decision_capability_allows_documented_question_and_fields(monkeypatch):
    decision = _decision()
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability",
        lambda model, provider, *, scoped_only: SimpleNamespace(decision=decision),
    )

    found = validate_model_decision_request(
        provider="openai",
        model="gpt-6-luna",
        request=_request("boolean"),
        question_kinds={"boolean": "predicate"},
        required_answer_fields={"boolean": ("probability",)},
        error_type=CapabilityError,
    )

    assert found is decision


def test_decision_capability_rejects_undocumented_question_kind(monkeypatch):
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability",
        lambda *_args, **_kwargs: SimpleNamespace(
            decision=_decision(question_kinds=("noul",))
        ),
    )

    with pytest.raises(CapabilityError, match="does not support 'predicate'"):
        validate_model_decision_request(
            provider="openai",
            model="gpt-6-luna",
            request=_request("boolean"),
            question_kinds={"boolean": "predicate"},
            required_answer_fields={"boolean": ("probability",)},
            error_type=CapabilityError,
        )


def test_decision_capability_rejects_missing_documented_answer_field(monkeypatch):
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability",
        lambda *_args, **_kwargs: SimpleNamespace(
            decision=_decision(answer_fields=("choice", "score"))
        ),
    )

    with pytest.raises(CapabilityError, match="probability"):
        validate_model_decision_request(
            provider="openai",
            model="gpt-6-luna",
            request=_request("boolean"),
            question_kinds={"boolean": "predicate"},
            required_answer_fields={"boolean": ("probability",)},
            error_type=CapabilityError,
        )


def test_decision_capability_rejects_models_marked_unsupported(monkeypatch):
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability",
        lambda *_args, **_kwargs: SimpleNamespace(decision=_decision(supported=False)),
    )

    with pytest.raises(CapabilityError, match="not documented as supporting"):
        validate_model_decision_request(
            provider="openai",
            model="chat-only-model",
            request=_request("boolean"),
            question_kinds={"boolean": "predicate"},
            required_answer_fields={"boolean": ("probability",)},
            error_type=CapabilityError,
        )


def test_unknown_model_capability_does_not_block_custom_deployments(monkeypatch):
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability",
        lambda *_args, **_kwargs: None,
    )

    assert (
        validate_model_decision_request(
            provider="openai",
            model="custom-decision-model",
            request=_request("boolean"),
            question_kinds={"boolean": "predicate"},
            required_answer_fields={"boolean": ("probability",)},
            error_type=CapabilityError,
        )
        is None
    )

"""Local Laya decision-provider adapter."""

from __future__ import annotations

import importlib
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from .models import (
    DecisionAnswer,
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
)
from .settings import DecisionSettings


class LayaDecisionError(RuntimeError):
    """Base error raised by the Laya decision adapter."""


class LayaDecisionConfigurationError(LayaDecisionError):
    """Raised when active Laya configuration is invalid."""


class LayaDecisionUnavailableError(LayaDecisionError):
    """Raised when the optional Laya runtime cannot be loaded."""


@dataclass(frozen=True)
class LayaDecisionConfig:
    """Resolved Laya-specific configuration."""

    model: str = "laya-multilingual"
    device: str = "auto"

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "LayaDecisionConfig":
        env = os.environ if environ is None else environ
        model = (
            str(env.get("UAGENT_DECISION_LAYA_DEPNAME") or "laya-multilingual").strip()
            or "laya-multilingual"
        )
        device = str(env.get("UAGENT_DECISION_LAYA_DEVICE") or "auto").strip() or "auto"
        return cls(model=model, device=device)


def _boolean_criteria(question: DecisionQuestion) -> dict[str, Any] | None:
    raw = question.metadata.get("criteria")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise LayaDecisionError(
            f"Boolean question '{question.id}' metadata.criteria must be a mapping."
        )
    return {
        "true": raw.get("true"),
        "false": raw.get("false"),
    }


def _choice_criteria(question: DecisionQuestion) -> dict[str, Any]:
    if not question.choices:
        raise LayaDecisionError(
            f"Choice question '{question.id}' requires at least one choice."
        )

    labels = [str(choice) for choice in question.choices]
    if len(set(labels)) != len(labels):
        raise LayaDecisionError(
            f"Choice question '{question.id}' contains duplicate choice labels."
        )

    descriptions = question.metadata.get("criteria")
    if descriptions is None:
        return {label: None for label in labels}
    if not isinstance(descriptions, Mapping):
        raise LayaDecisionError(
            f"Choice question '{question.id}' metadata.criteria must be a mapping."
        )
    return {label: descriptions.get(label) for label in labels}


def _score_criteria(question: DecisionQuestion) -> list[Any]:
    raw = question.metadata.get("criteria")
    if raw is not None and not isinstance(raw, (list, tuple)):
        raise LayaDecisionError(
            f"Score question '{question.id}' metadata.criteria must be a list or tuple."
        )
    criteria = list(raw) if raw is not None else list(question.choices)
    if len(criteria) < 2:
        raise LayaDecisionError(
            f"Score question '{question.id}' requires at least two ordered levels."
        )
    return criteria


def _translate_question(question: DecisionQuestion) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instructions": question.instruction,
    }

    if question.kind == DecisionKind.BOOLEAN:
        payload["type"] = "noul"
        criteria = _boolean_criteria(question)
        if criteria is not None:
            payload["criteria"] = criteria
        return payload

    if question.kind == DecisionKind.CHOICE:
        payload["type"] = "choice"
        payload["criteria"] = _choice_criteria(question)
        return payload

    if question.kind == DecisionKind.SCORE:
        payload["type"] = "score"
        payload["criteria"] = _score_criteria(question)
        return payload

    raise LayaDecisionError(f"Unsupported decision kind: {question.kind!s}")


def _answer_confidence(question: DecisionQuestion, payload: Mapping[str, Any]) -> float:
    try:
        confidence = float(payload["answer_confidence"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LayaDecisionError(
            f"Laya answer for '{question.id}' is missing a valid answer_confidence."
        ) from exc
    if not 0.0 <= confidence <= 1.0:
        raise LayaDecisionError(
            f"Laya answer_confidence for '{question.id}' is outside [0, 1]."
        )
    return confidence


def _common_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "type": payload.get("type"),
    }
    if "confidence" in payload:
        metadata["entropy_confidence"] = payload.get("confidence")
    action = payload.get("action")
    if isinstance(action, Mapping) and "act_probability" in action:
        metadata["act_probability"] = action.get("act_probability")
    return metadata


def _translate_answer(
    question: DecisionQuestion,
    payload: Any,
) -> DecisionAnswer:
    if not isinstance(payload, Mapping):
        raise LayaDecisionError(f"Laya answer for '{question.id}' is not an object.")

    expected_type = {
        DecisionKind.BOOLEAN: "noul",
        DecisionKind.CHOICE: "choice",
        DecisionKind.SCORE: "score",
    }[question.kind]
    answer_type = str(payload.get("type") or "")
    if answer_type != expected_type:
        raise LayaDecisionError(
            f"Laya answer for '{question.id}' has type '{answer_type}', "
            f"expected '{expected_type}'."
        )

    confidence = _answer_confidence(question, payload)
    metadata = _common_metadata(payload)

    if question.kind == DecisionKind.BOOLEAN:
        try:
            probability_true = float(payload["noul"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LayaDecisionError(
                f"Laya noul answer for '{question.id}' is missing a valid probability."
            ) from exc
        if not 0.0 <= probability_true <= 1.0:
            raise LayaDecisionError(
                f"Laya noul answer for '{question.id}' is outside [0, 1]."
            )
        metadata["probability_true"] = probability_true
        return DecisionAnswer(
            value=probability_true >= 0.5,
            confidence=confidence,
            calibrated=False,
            metadata=metadata,
        )

    if question.kind == DecisionKind.CHOICE:
        value = payload.get("choice")
        if value is None:
            raise LayaDecisionError(
                f"Laya choice answer for '{question.id}' is missing 'choice'."
            )
        allowed = {str(choice) for choice in question.choices}
        if str(value) not in allowed:
            raise LayaDecisionError(
                f"Laya choice answer for '{question.id}' returned "
                f"unrecognized choice '{value}'."
            )
        probabilities = payload.get("probabilities")
        if not isinstance(probabilities, Mapping):
            raise LayaDecisionError(
                f"Laya choice answer for '{question.id}' is missing probabilities."
            )
        metadata["probabilities"] = dict(probabilities)
        return DecisionAnswer(
            value=value,
            confidence=confidence,
            calibrated=False,
            metadata=metadata,
        )

    try:
        score = float(payload["score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LayaDecisionError(
            f"Laya score answer for '{question.id}' is missing a valid score."
        ) from exc

    criteria = _score_criteria(question)
    if not 0.0 <= score <= float(len(criteria) - 1):
        raise LayaDecisionError(
            f"Laya score answer for '{question.id}' is outside the requested "
            "rubric range."
        )

    probabilities = payload.get("probabilities")
    legend = payload.get("legend")
    if not isinstance(probabilities, Mapping) or not isinstance(legend, Mapping):
        raise LayaDecisionError(
            f"Laya score answer for '{question.id}' is missing " "probabilities/legend."
        )
    metadata["probabilities"] = dict(probabilities)
    metadata["legend"] = dict(legend)
    return DecisionAnswer(
        value=score,
        confidence=confidence,
        calibrated=False,
        metadata=metadata,
    )


def _canonical_model_name(value: Any, fallback: str) -> str:
    aliases = {
        "english": "laya",
        "laya": "laya",
        "multilingual": "laya-multilingual",
        "laya-multilingual": "laya-multilingual",
        "typed-decisions": "laya-typed-decisions",
        "laya-typed-decisions": "laya-typed-decisions",
    }
    raw = str(value or "").strip()
    return aliases.get(raw, raw or fallback)


class LayaDecisionProvider:
    """Decision provider backed by a local, lazily loaded Laya Router."""

    def __init__(
        self,
        *,
        settings: DecisionSettings,
        environ: Mapping[str, str] | None = None,
        router: Any = None,
        module_loader: Callable[[str], Any] | None = None,
    ) -> None:
        if settings.provider != "laya":
            raise LayaDecisionConfigurationError(
                "LayaDecisionProvider requires provider='laya'."
            )

        self._settings = settings
        self._config = LayaDecisionConfig.from_environment(environ)
        self._router = router
        self._owns_router = router is None
        self._module_loader = module_loader or importlib.import_module
        self._closed = False

    @property
    def name(self) -> str:
        return "laya"

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def device(self) -> str:
        return self._config.device

    def _get_router(self) -> Any:
        if self._router is not None:
            return self._router

        try:
            module = self._module_loader("laya")
        except ModuleNotFoundError as exc:
            raise LayaDecisionUnavailableError(
                "Laya is selected as the Decision Provider but the optional "
                "runtime is not installed. Install 'uag[decision-laya]' or "
                "'laya>=0.3.23,<0.4'."
            ) from exc
        except Exception as exc:
            raise LayaDecisionUnavailableError(
                f"Failed to import the Laya runtime: {type(exc).__name__}."
            ) from exc

        router_class = getattr(module, "Router", None)
        if router_class is None:
            raise LayaDecisionUnavailableError(
                "The installed Laya runtime does not expose laya.Router."
            )

        device = None if self._config.device.lower() == "auto" else self._config.device
        try:
            self._router = router_class(
                device=device,
                max_loaded=1,
                preload=False,
            )
        except Exception as exc:
            raise LayaDecisionUnavailableError(
                f"Failed to initialize the Laya Router: {type(exc).__name__}."
            ) from exc
        return self._router

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if self._closed:
            raise LayaDecisionError("Laya decision provider is closed.")
        if not request.questions:
            raise LayaDecisionError("Decision request requires at least one question.")
        if not isinstance(request.state, (str, dict, list)):
            raise LayaDecisionError(
                "Laya decision state must be a string, mapping, or list."
            )

        question_ids = [question.id for question in request.questions]
        if len(set(question_ids)) != len(question_ids):
            raise LayaDecisionError("Decision request contains duplicate question ids.")

        questions = {
            question.id: _translate_question(question) for question in request.questions
        }
        router = self._get_router()

        started = time.perf_counter()
        try:
            data = router.predict(
                request.state,
                questions,
                model=self._config.model,
            )
        except Exception as exc:
            if isinstance(exc, LayaDecisionError):
                raise
            raise LayaDecisionError(
                f"Laya decision request failed: {type(exc).__name__}."
            ) from exc

        if not isinstance(data, Mapping):
            raise LayaDecisionError("Laya decision response is not an object.")

        raw_answers = data.get("answers")
        if not isinstance(raw_answers, Mapping):
            raise LayaDecisionError(
                "Laya decision response is missing an answers object."
            )

        answers: dict[str, DecisionAnswer] = {}
        for question in request.questions:
            if question.id not in raw_answers:
                raise LayaDecisionError(
                    f"Laya decision response is missing answer '{question.id}'."
                )
            answers[question.id] = _translate_answer(
                question,
                raw_answers[question.id],
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        routing = data.get("routing")
        routed_model = routing.get("model") if isinstance(routing, Mapping) else None
        result_model = _canonical_model_name(
            routed_model,
            self._config.model,
        )
        return DecisionResult(
            provider="laya",
            model=result_model,
            answers=answers,
            latency_ms=latency_ms,
            skipped=False,
            raw=dict(data),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_router and self._router is not None:
            closer = getattr(self._router, "close", None)
            if callable(closer):
                closer()

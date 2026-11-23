"""Google Gemini Decisions API adapter."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..auth.credential_store import get_default_credential_store
from ..auth.provider_credentials import get_provider_api_key
from ..providers.util_providers import make_httpx_client
from ..utils.secret_mask import _mask_inline_secrets
from .capabilities import validate_model_decision_request
from .models import (
    DecisionAnswer,
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
)
from .settings import DecisionSettings


class GoogleDecisionError(RuntimeError):
    """Base error raised by the Google Gemini Decisions API adapter."""


class GoogleDecisionConfigurationError(GoogleDecisionError):
    """Raised when active Google decision configuration is incomplete."""


@dataclass(frozen=True)
class GoogleDecisionConfig:
    """Resolved Google Gemini Decisions API configuration."""

    model: str = "gemini-decision-1"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    api_key: str = field(default="", repr=False)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "GoogleDecisionConfig":
        env = os.environ if environ is None else environ
        model = (
            str(
                env.get("UAGENT_DECISION_GOOGLE_DEPNAME") or "gemini-decision-1"
            ).strip()
            or "gemini-decision-1"
        )
        base_url = (
            str(
                env.get("UAGENT_DECISION_GOOGLE_BASE_URL")
                or "https://generativelanguage.googleapis.com/v1beta"
            ).strip()
            or "https://generativelanguage.googleapis.com/v1beta"
        )
        api_key = str(env.get("UAGENT_DECISION_GOOGLE_API_KEY") or "").strip()
        if not api_key:
            store = None
            if environ is None:
                try:
                    store = get_default_credential_store()
                except Exception:
                    store = None
            api_key = str(
                get_provider_api_key("google", store=store, environ=env) or ""
            ).strip()
        if not api_key:
            raise GoogleDecisionConfigurationError(
                "Google Decision Provider requires UAGENT_DECISION_GOOGLE_API_KEY, "
                "a stored Google credential, UAGENT_GEMINI_API_KEY, "
                "UAGENT_GOOGLE_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY."
            )
        return cls(model=model, base_url=base_url.rstrip("/"), api_key=api_key)


def _decisions_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/v1beta/decisions") or normalized.endswith("/decisions"):
        return normalized
    if normalized.endswith("/v1beta") or normalized.endswith("/v1"):
        return normalized + "/decisions"
    return normalized + "/v1beta/decisions"


def _safe_response_error_detail(response: Any, *, secret: str) -> str:
    try:
        data = response.json()
    except Exception:
        data = None
    value: Any = ""
    if isinstance(data, Mapping):
        error = data.get("error")
        value = error.get("message", "") if isinstance(error, Mapping) else error
    if not value:
        try:
            value = getattr(response, "text", "") or ""
        except Exception:
            value = ""
    detail = " ".join(str(value or "").split())
    if not detail:
        return ""
    if secret:
        detail = detail.replace(secret, "********")
    return _mask_inline_secrets(detail)[:300]


def _state_to_input(state: Any, metadata: Mapping[str, Any]) -> str:
    if not isinstance(state, (str, Mapping, list)):
        raise GoogleDecisionError(
            "Google decision state must be a string, mapping, or list."
        )
    value: Any = state
    if metadata:
        value = {"state": state, "metadata": dict(metadata)}
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise GoogleDecisionError(
            "Google decision input must be JSON-serializable."
        ) from exc


def _score_levels(question: DecisionQuestion) -> list[str]:
    raw = question.metadata.get("criteria")
    if raw is not None and not isinstance(raw, (list, tuple)):
        raise GoogleDecisionError(
            f"Score question '{question.id}' metadata.criteria must be a list or tuple."
        )
    source_levels = list(raw) if raw is not None else list(question.choices)
    levels: list[str] = []
    for level in source_levels:
        if isinstance(level, Mapping):
            description = level.get(
                "description", level.get("label", level.get("value", ""))
            )
        else:
            description = level
        text = str(description if description is not None else "").strip()
        if not text:
            raise GoogleDecisionError(
                f"Score question '{question.id}' has an empty rubric level."
            )
        levels.append(text)
    if not 2 <= len(levels) <= 255:
        raise GoogleDecisionError(
            f"Score question '{question.id}' requires 2 to 255 ordered levels."
        )
    return levels


def _question_payload(question: DecisionQuestion) -> dict[str, Any]:
    payload: dict[str, Any] = {"instructions": str(question.instruction or "")}
    if question.kind == DecisionKind.BOOLEAN:
        payload["type"] = "noul"
        raw_criteria = question.metadata.get("criteria")
        if raw_criteria is not None:
            if not isinstance(raw_criteria, Mapping):
                raise GoogleDecisionError(
                    f"Boolean question '{question.id}' metadata.criteria must be a mapping."
                )
            true_description = raw_criteria.get(
                "true_description", raw_criteria.get("true", "")
            )
            false_description = raw_criteria.get(
                "false_description", raw_criteria.get("false", "")
            )
            payload["criteria"] = {
                "true_description": str(true_description or ""),
                "false_description": str(false_description or ""),
            }
    elif question.kind == DecisionKind.CHOICE:
        if not 2 <= len(question.choices) <= 255:
            raise GoogleDecisionError(
                f"Choice question '{question.id}' requires 2 to 255 choices."
            )
        labels = [str(choice) for choice in question.choices]
        if any(not label for label in labels) or len(set(labels)) != len(labels):
            raise GoogleDecisionError(
                f"Choice question '{question.id}' contains empty or duplicate choice IDs."
            )
        descriptions = question.metadata.get("criteria")
        if descriptions is not None and not isinstance(descriptions, Mapping):
            raise GoogleDecisionError(
                f"Choice question '{question.id}' metadata.criteria must be a mapping."
            )
        payload["type"] = "choice"
        payload["criteria"] = {
            label: str((descriptions or {}).get(label) or "") for label in labels
        }
    elif question.kind == DecisionKind.SCORE:
        payload["type"] = "score"
        payload["criteria"] = _score_levels(question)
    else:
        raise GoogleDecisionError(f"Unsupported decision kind: {question.kind!s}")
    return payload


def _build_request_payload(request: DecisionRequest, model: str) -> dict[str, Any]:
    if len(request.questions) > 1000:
        raise GoogleDecisionError(
            "Google Decisions API supports at most 1000 questions per request."
        )
    question_ids = [question.id for question in request.questions]
    if any(
        not isinstance(question_id, str) or not question_id.strip()
        for question_id in question_ids
    ):
        raise GoogleDecisionError("Decision question IDs must be non-empty strings.")
    if len(set(question_ids)) != len(question_ids):
        raise GoogleDecisionError("Decision request contains duplicate question ids.")
    return {
        "model": model,
        "input": _state_to_input(request.state, request.metadata),
        "questions": {
            question.id: _question_payload(question) for question in request.questions
        },
    }


def _probability(
    value: Any,
    *,
    label: str,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GoogleDecisionError(
            f"Google {label} must be a number in [{minimum:g}, {maximum:g}]."
        ) from exc
    if not minimum <= number <= maximum:
        raise GoogleDecisionError(
            f"Google {label} is outside [{minimum:g}, {maximum:g}]."
        )
    return number


def _translate_probabilities(
    value: Any,
    *,
    label: str,
    expected_keys: set[str],
) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise GoogleDecisionError(f"Google {label} must be an object.")
    probabilities: dict[str, float] = {}
    for key, probability in value.items():
        normalized_key = str(key)
        if normalized_key in probabilities:
            raise GoogleDecisionError(f"Google {label} contains duplicate keys.")
        probabilities[normalized_key] = _probability(
            probability, label=f"{label} probability for '{normalized_key}'"
        )
    if set(probabilities) != expected_keys:
        raise GoogleDecisionError(
            f"Google {label} does not match the requested options."
        )
    return probabilities


def _translate_answer(question: DecisionQuestion, payload: Any) -> DecisionAnswer:
    if not isinstance(payload, Mapping):
        raise GoogleDecisionError(
            f"Google answer for '{question.id}' is not an object."
        )
    expected_type = {
        DecisionKind.BOOLEAN: "noul",
        DecisionKind.CHOICE: "choice",
        DecisionKind.SCORE: "score",
    }[question.kind]
    answer_type = str(payload.get("type") or "")
    if answer_type != expected_type:
        raise GoogleDecisionError(
            f"Google answer for '{question.id}' has type '{answer_type}', "
            f"expected '{expected_type}'."
        )
    confidence = _probability(
        payload.get("confidence"), label=f"confidence for '{question.id}'"
    )

    if question.kind == DecisionKind.BOOLEAN:
        probability_true = _probability(
            payload.get("noul"),
            label=f"noul probability for '{question.id}'",
            minimum=0.01,
            maximum=0.99,
        )
        return DecisionAnswer(
            value=probability_true >= 0.5,
            confidence=confidence,
            calibrated=True,
            metadata={"type": "noul", "probability_true": probability_true},
        )

    if question.kind == DecisionKind.CHOICE:
        allowed = {str(choice): choice for choice in question.choices}
        selected = str(payload.get("choice") or "")
        if selected not in allowed:
            raise GoogleDecisionError(
                f"Google choice answer for '{question.id}' returned an unrecognized choice."
            )
        probabilities = _translate_probabilities(
            payload.get("probabilities"),
            label=f"choice probabilities for '{question.id}'",
            expected_keys=set(allowed),
        )
        return DecisionAnswer(
            value=allowed[selected],
            confidence=confidence,
            calibrated=True,
            metadata={"type": "choice", "probabilities": probabilities},
        )

    levels = _score_levels(question)
    try:
        score = float(payload.get("score"))
    except (TypeError, ValueError) as exc:
        raise GoogleDecisionError(
            f"Google score answer for '{question.id}' is missing a valid score."
        ) from exc
    if not 0.0 <= score <= float(len(levels) - 1):
        raise GoogleDecisionError(
            f"Google score for '{question.id}' is outside the requested rubric range."
        )
    expected_indices = {str(index) for index in range(len(levels))}
    probabilities = _translate_probabilities(
        payload.get("probabilities"),
        label=f"score probabilities for '{question.id}'",
        expected_keys=expected_indices,
    )
    raw_legend = payload.get("legend")
    if not isinstance(raw_legend, Mapping):
        raise GoogleDecisionError(
            f"Google score legend for '{question.id}' must be an object."
        )
    legend = {str(key): str(value) for key, value in raw_legend.items()}
    if set(legend) != expected_indices:
        raise GoogleDecisionError(
            f"Google score legend for '{question.id}' does not match the requested rubric."
        )
    return DecisionAnswer(
        value=score,
        confidence=confidence,
        calibrated=True,
        metadata={"type": "score", "probabilities": probabilities, "legend": legend},
    )


class GoogleDecisionProvider:
    """Decision provider backed by Google's native Gemini Decisions API."""

    def __init__(
        self,
        *,
        settings: DecisionSettings,
        environ: Mapping[str, str] | None = None,
        client: Any = None,
    ) -> None:
        if settings.provider != "google":
            raise GoogleDecisionConfigurationError(
                "GoogleDecisionProvider requires provider='google'."
            )
        self._settings = settings
        self._config = GoogleDecisionConfig.from_environment(environ)
        self._owns_client = client is None
        self._client = client or make_httpx_client() or httpx.Client(timeout=30.0)
        self._closed = False

    @property
    def name(self) -> str:
        return "google"

    @property
    def model(self) -> str:
        return self._config.model

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if self._closed:
            raise GoogleDecisionError("Google decision provider is closed.")
        if not request.questions:
            raise GoogleDecisionError(
                "Decision request requires at least one question."
            )
        validate_model_decision_request(
            provider="google",
            model=self._config.model,
            request=request,
            question_kinds={
                "boolean": "noul",
                "choice": "choice",
                "score": "score",
            },
            required_answer_fields={
                "boolean": ("noul", "confidence"),
                "choice": ("choice", "probabilities", "confidence"),
                "score": ("score", "probabilities", "legend", "confidence"),
            },
            error_type=GoogleDecisionError,
        )
        payload = _build_request_payload(request, self._config.model)
        headers = {
            "x-goog-api-key": self._config.api_key,
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        try:
            response = self._client.post(
                _decisions_url(self._config.base_url),
                headers=headers,
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise GoogleDecisionError(
                f"Google decision request failed: {type(exc).__name__}."
            ) from exc

        status_code = int(getattr(response, "status_code", 0) or 0)
        if not 200 <= status_code < 300:
            detail = _safe_response_error_detail(response, secret=self._config.api_key)
            suffix = f": {detail}" if detail else "."
            raise GoogleDecisionError(
                f"Google decision request failed with HTTP {status_code}{suffix}"
            )
        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise GoogleDecisionError(
                "Google decision response was not valid JSON."
            ) from exc
        if not isinstance(data, Mapping):
            raise GoogleDecisionError("Google decision response is not an object.")
        raw_answers = data.get("answers")
        if not isinstance(raw_answers, Mapping):
            raise GoogleDecisionError(
                "Google decision response is missing an answers object."
            )

        question_ids = {question.id for question in request.questions}
        answers_by_id = {str(key): value for key, value in raw_answers.items()}
        if len(answers_by_id) != len(raw_answers):
            raise GoogleDecisionError(
                "Google decision response contains duplicate answer IDs."
            )
        unexpected = set(answers_by_id) - question_ids
        if unexpected:
            raise GoogleDecisionError(
                "Google decision response contains an unexpected answer."
            )
        answers: dict[str, DecisionAnswer] = {}
        for question in request.questions:
            if question.id not in answers_by_id:
                raise GoogleDecisionError(
                    f"Google decision response is missing answer '{question.id}'."
                )
            answers[question.id] = _translate_answer(
                question, answers_by_id[question.id]
            )

        return DecisionResult(
            provider="google",
            model=str(data.get("model") or self._config.model),
            answers=answers,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            skipped=False,
            raw=dict(data),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self._client.close()

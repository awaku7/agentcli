"""OpenAI Decisions API adapter."""

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
from .models import (
    DecisionAnswer,
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
)
from .settings import DecisionSettings
from ..utils.secret_mask import _mask_inline_secrets


class OpenAIDecisionError(RuntimeError):
    """Base error raised by the OpenAI Decisions API adapter."""


class OpenAIDecisionConfigurationError(OpenAIDecisionError):
    """Raised when active OpenAI decision configuration is incomplete."""


@dataclass(frozen=True)
class OpenAIDecisionConfig:
    """Resolved OpenAI Decisions API configuration."""

    model: str = "gpt-6-luna"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = field(default="", repr=False)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "OpenAIDecisionConfig":
        env = os.environ if environ is None else environ
        model = (
            str(env.get("UAGENT_DECISION_OPENAI_DEPNAME") or "gpt-6-luna").strip()
            or "gpt-6-luna"
        )
        base_url = (
            str(
                env.get("UAGENT_DECISION_OPENAI_BASE_URL")
                or "https://api.openai.com/v1"
            ).strip()
            or "https://api.openai.com/v1"
        )
        api_key = str(env.get("UAGENT_DECISION_OPENAI_API_KEY") or "").strip()
        if not api_key:
            store = None
            if environ is None:
                try:
                    store = get_default_credential_store()
                except Exception:
                    store = None
            api_key = str(
                get_provider_api_key("openai", store=store, environ=env) or ""
            ).strip()
        if not api_key:
            raise OpenAIDecisionConfigurationError(
                "OpenAI Decision Provider requires UAGENT_DECISION_OPENAI_API_KEY, "
                "a stored OpenAI credential, UAGENT_OPENAI_API_KEY, or OPENAI_API_KEY."
            )
        return cls(model=model, base_url=base_url.rstrip("/"), api_key=api_key)


def _decisions_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/v1/decisions"):
        return normalized
    if normalized.endswith("/v1"):
        return normalized + "/decisions"
    return normalized + "/v1/decisions"


def _safe_response_error_detail(
    response: Any,
    *,
    secrets: tuple[str, ...] = (),
) -> str:
    try:
        data = response.json()
    except Exception:
        data = None
    value: Any = ""
    if isinstance(data, Mapping):
        value = data.get("detail") or data.get("message") or data.get("error") or ""
        if isinstance(value, (Mapping, list)):
            try:
                value = json.dumps(value, ensure_ascii=False)
            except Exception:
                value = str(value)
    if not value:
        try:
            value = getattr(response, "text", "") or ""
        except Exception:
            value = ""
    detail = " ".join(str(value or "").split())
    if not detail:
        return ""
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, "********")
    return _mask_inline_secrets(detail)[:300]


def _score_criteria(question: DecisionQuestion) -> list[Any]:
    raw = question.metadata.get("criteria")
    if raw is not None and not isinstance(raw, (list, tuple)):
        raise OpenAIDecisionError(
            f"Score question '{question.id}' metadata.criteria must be a list or tuple."
        )
    criteria = list(raw) if raw is not None else list(question.choices)
    if len(criteria) < 2:
        raise OpenAIDecisionError(
            f"Score question '{question.id}' requires at least two ordered levels."
        )
    return criteria


def _state_to_input(state: Any) -> str:
    if isinstance(state, str):
        return state
    if not isinstance(state, (Mapping, list)):
        raise OpenAIDecisionError(
            "OpenAI decision state must be a string, mapping, or list."
        )
    try:
        return json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise OpenAIDecisionError(
            "OpenAI decision state must be JSON-serializable."
        ) from exc


def _predicate_instructions(question: DecisionQuestion) -> str:
    instruction = str(question.instruction or "")
    criteria = question.metadata.get("criteria")
    if criteria is None:
        return instruction
    if not isinstance(criteria, Mapping):
        raise OpenAIDecisionError(
            f"Boolean question '{question.id}' metadata.criteria must be a mapping."
        )
    details = []
    for answer in ("true", "false"):
        description = criteria.get(answer)
        if description is not None and str(description).strip():
            details.append(f"{answer.upper()} means: {str(description).strip()}")
    if details:
        return instruction + "\n\n" + " ".join(details)
    return instruction


def _translate_question(question: DecisionQuestion) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": question.id,
        "instructions": str(question.instruction or ""),
    }
    if question.kind == DecisionKind.BOOLEAN:
        payload["type"] = "predicate"
        payload["instructions"] = _predicate_instructions(question)
    elif question.kind == DecisionKind.CHOICE:
        if not question.choices:
            raise OpenAIDecisionError(
                f"Choice question '{question.id}' requires at least one choice."
            )
        labels = [str(choice) for choice in question.choices]
        if len(set(labels)) != len(labels):
            raise OpenAIDecisionError(
                f"Choice question '{question.id}' contains duplicate choice labels."
            )
        descriptions = question.metadata.get("criteria")
        if descriptions is not None and not isinstance(descriptions, Mapping):
            raise OpenAIDecisionError(
                f"Choice question '{question.id}' metadata.criteria must be a mapping."
            )
        payload["type"] = "choice"
        payload["choices"] = [
            {
                "value": label,
                "description": str((descriptions or {}).get(label) or ""),
            }
            for label in labels
        ]
    elif question.kind == DecisionKind.SCORE:
        try:
            criteria = _score_criteria(question)
        except Exception as exc:
            raise OpenAIDecisionError(str(exc)) from exc

        source_levels = list(question.choices) or list(criteria)
        if question.choices and len(source_levels) != len(criteria):
            raise OpenAIDecisionError(
                f"Score question '{question.id}' has a different number of choices "
                "and criteria."
            )
        levels: list[dict[str, str]] = []
        for index, source_level in enumerate(source_levels):
            criterion = criteria[index] if index < len(criteria) else source_level
            if isinstance(source_level, Mapping):
                label = source_level.get("label", source_level.get("value", index))
                description = source_level.get("description", "")
            else:
                label = source_level
                description = criterion
                if isinstance(criterion, Mapping):
                    description = criterion.get("description", "")
            levels.append(
                {
                    "label": str(label),
                    "description": "" if description is None else str(description),
                }
            )
        payload["type"] = "score"
        payload["levels"] = levels
    else:
        raise OpenAIDecisionError(f"Unsupported decision kind: {question.kind!s}")
    return payload


def _translate_probability(value: Any, *, label: str) -> float:
    try:
        probability = float(value)
    except (TypeError, ValueError) as exc:
        raise OpenAIDecisionError(
            f"OpenAI {label} is missing a valid probability."
        ) from exc
    if not 0.0 <= probability <= 1.0:
        raise OpenAIDecisionError(f"OpenAI {label} probability is outside [0, 1].")
    return probability


def _translate_answer(question: DecisionQuestion, payload: Any) -> DecisionAnswer:
    if not isinstance(payload, Mapping):
        raise OpenAIDecisionError(
            f"OpenAI answer for '{question.id}' is not an object."
        )
    expected_type = {
        DecisionKind.BOOLEAN: "predicate",
        DecisionKind.CHOICE: "choice",
        DecisionKind.SCORE: "score",
    }[question.kind]
    answer_type = str(payload.get("type") or "")
    if answer_type != expected_type:
        raise OpenAIDecisionError(
            f"OpenAI answer for '{question.id}' has type '{answer_type}', "
            f"expected '{expected_type}'."
        )

    if question.kind == DecisionKind.BOOLEAN:
        probability_true = _translate_probability(
            payload.get("probability"), label=f"predicate answer for '{question.id}'"
        )
        value = probability_true >= 0.5
        return DecisionAnswer(
            value=value,
            confidence=max(probability_true, 1.0 - probability_true),
            metadata={"type": "predicate", "probability_true": probability_true},
        )

    raw_probabilities = payload.get("probabilities")
    probabilities: dict[str, float] = {}
    if raw_probabilities is not None:
        if not isinstance(raw_probabilities, list):
            raise OpenAIDecisionError(
                f"OpenAI probabilities for '{question.id}' are not an array."
            )
        for item in raw_probabilities:
            if not isinstance(item, Mapping) or "value" not in item:
                raise OpenAIDecisionError(
                    f"OpenAI probabilities for '{question.id}' contain an invalid item."
                )
            key = str(item["value"])
            if key in probabilities:
                raise OpenAIDecisionError(
                    f"OpenAI probabilities for '{question.id}' contain duplicate values."
                )
            probabilities[key] = _translate_probability(
                item.get("probability"), label=f"probability for '{question.id}'"
            )

    if question.kind == DecisionKind.CHOICE:
        selected = payload.get("choice")
        if selected is None:
            raise OpenAIDecisionError(
                f"OpenAI choice answer for '{question.id}' is missing 'choice'."
            )
        allowed = {str(choice): choice for choice in question.choices}
        selected_key = str(selected)
        if selected_key not in allowed:
            raise OpenAIDecisionError(
                f"OpenAI choice answer for '{question.id}' returned "
                f"unrecognized choice '{selected}'."
            )
        provider_confidence = None
        if payload.get("confidence") is not None:
            provider_confidence = _translate_probability(
                payload["confidence"], label=f"choice confidence for '{question.id}'"
            )
        confidence = probabilities.get(selected_key, provider_confidence)
        metadata: dict[str, Any] = {"type": "choice"}
        if probabilities:
            metadata["probabilities"] = probabilities
        if provider_confidence is not None:
            metadata["provider_confidence"] = provider_confidence
        return DecisionAnswer(
            value=allowed[selected_key],
            confidence=confidence,
            metadata=metadata,
        )

    try:
        score = float(payload["score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenAIDecisionError(
            f"OpenAI score answer for '{question.id}' is missing a valid score."
        ) from exc
    try:
        criteria = _score_criteria(question)
    except Exception as exc:
        raise OpenAIDecisionError(str(exc)) from exc
    if not 0.0 <= score <= float(len(criteria) - 1):
        raise OpenAIDecisionError(
            f"OpenAI score for '{question.id}' is outside the requested rubric range."
        )
    confidence = None
    if payload.get("confidence") is not None:
        confidence = _translate_probability(
            payload["confidence"], label=f"score confidence for '{question.id}'"
        )
    return DecisionAnswer(
        value=score,
        confidence=confidence,
        metadata={
            "type": "score",
            "probabilities": probabilities,
            "provider_confidence": confidence,
        },
    )


class OpenAIDecisionProvider:
    """Decision provider backed by OpenAI's native Decisions API."""

    def __init__(
        self,
        *,
        settings: DecisionSettings,
        environ: Mapping[str, str] | None = None,
        client: Any = None,
    ) -> None:
        if settings.provider != "openai":
            raise OpenAIDecisionConfigurationError(
                "OpenAIDecisionProvider requires provider='openai'."
            )
        self._settings = settings
        self._config = OpenAIDecisionConfig.from_environment(environ)
        self._owns_client = client is None
        if client is not None:
            self._client = client
        else:
            self._client = make_httpx_client() or httpx.Client(timeout=30.0)
        self._closed = False

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._config.model

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if self._closed:
            raise OpenAIDecisionError("OpenAI decision provider is closed.")
        if not request.questions:
            raise OpenAIDecisionError(
                "Decision request requires at least one question."
            )
        question_ids = [question.id for question in request.questions]
        if len(set(question_ids)) != len(question_ids):
            raise OpenAIDecisionError(
                "Decision request contains duplicate question ids."
            )

        payload = {
            "model": self._config.model,
            "input": _state_to_input(request.state),
            "questions": [
                _translate_question(question) for question in request.questions
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
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
            raise OpenAIDecisionError(
                f"OpenAI decision request failed: {type(exc).__name__}."
            ) from exc

        status_code = int(getattr(response, "status_code", 0) or 0)
        if not 200 <= status_code < 300:
            detail = _safe_response_error_detail(
                response,
                secrets=(self._config.api_key,),
            )
            suffix = f": {detail}" if detail else "."
            raise OpenAIDecisionError(
                f"OpenAI decision request failed with HTTP {status_code}{suffix}"
            )
        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise OpenAIDecisionError(
                "OpenAI decision response was not valid JSON."
            ) from exc
        if not isinstance(data, Mapping):
            raise OpenAIDecisionError("OpenAI decision response is not an object.")
        raw_answers = data.get("answers")
        if not isinstance(raw_answers, list):
            raise OpenAIDecisionError(
                "OpenAI decision response is missing an answers array."
            )
        answers_by_name: dict[str, Any] = {}
        for answer in raw_answers:
            if not isinstance(answer, Mapping) or not answer.get("name"):
                raise OpenAIDecisionError(
                    "OpenAI decision response contains an answer without a name."
                )
            name = str(answer["name"])
            if name in answers_by_name:
                raise OpenAIDecisionError(
                    f"OpenAI decision response contains duplicate answer '{name}'."
                )
            answers_by_name[name] = answer

        answers: dict[str, DecisionAnswer] = {}
        for question in request.questions:
            if question.id not in answers_by_name:
                raise OpenAIDecisionError(
                    f"OpenAI decision response is missing answer '{question.id}'."
                )
            answers[question.id] = _translate_answer(
                question, answers_by_name[question.id]
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        return DecisionResult(
            provider="openai",
            model=str(data.get("model") or self._config.model),
            answers=answers,
            latency_ms=latency_ms,
            skipped=False,
            raw=dict(data),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self._client.close()

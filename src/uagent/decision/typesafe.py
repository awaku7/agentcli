"""TypeSafe/Jev decision-provider adapter."""

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
from .models import (
    DecisionAnswer,
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
)
from .settings import DecisionSettings


class TypeSafeDecisionError(RuntimeError):
    """Base error raised by the TypeSafe decision adapter."""


class TypeSafeDecisionConfigurationError(TypeSafeDecisionError):
    """Raised when active TypeSafe configuration is incomplete or invalid."""


@dataclass(frozen=True)
class TypeSafeDecisionConfig:
    """Resolved TypeSafe-specific configuration."""

    model: str = "jev-latest"
    base_url: str = "https://api.typesafe.ai"
    api_key: str = field(default="", repr=False)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "TypeSafeDecisionConfig":
        env = os.environ if environ is None else environ
        model = (
            str(env.get("UAGENT_DECISION_TYPESAFE_DEPNAME") or "jev-latest").strip()
            or "jev-latest"
        )
        base_url = (
            str(
                env.get("UAGENT_DECISION_TYPESAFE_BASE_URL")
                or "https://api.typesafe.ai"
            ).strip()
            or "https://api.typesafe.ai"
        )
        api_key = str(env.get("UAGENT_DECISION_TYPESAFE_API_KEY") or "").strip()
        if not api_key:
            store = None
            if environ is None:
                try:
                    store = get_default_credential_store()
                except Exception:
                    store = None
            api_key = str(
                get_provider_api_key("typesafe", store=store, environ=env) or ""
            ).strip()
        if not api_key:
            raise TypeSafeDecisionConfigurationError(
                "UAGENT_DECISION_TYPESAFE_API_KEY is required when "
                "UAGENT_DECISION_PROVIDER=typesafe."
            )
        return cls(model=model, base_url=base_url.rstrip("/"), api_key=api_key)


def _system_one_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/v1/systemone"):
        return normalized
    if normalized.endswith("/v1"):
        return normalized + "/systemone"
    return normalized + "/v1/systemone"


def _safe_response_error_detail(
    response: Any,
    *,
    secrets: tuple[str, ...] = (),
) -> str:
    value: Any = ""
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, Mapping):
        value = (
            payload.get("detail")
            or payload.get("message")
            or payload.get("error")
            or ""
        )
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


def _question_wire_type(kind: DecisionKind) -> str:
    if kind == DecisionKind.BOOLEAN:
        return "noul"
    if kind == DecisionKind.CHOICE:
        return "choice"
    if kind == DecisionKind.SCORE:
        return "score"
    raise TypeSafeDecisionError(f"Unsupported decision kind: {kind!s}")


def _boolean_criteria(question: DecisionQuestion) -> dict[str, Any] | None:
    raw = question.metadata.get("criteria")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TypeSafeDecisionError(
            f"Boolean question '{question.id}' metadata.criteria must be a mapping."
        )
    return {
        "true": raw.get("true"),
        "false": raw.get("false"),
    }


def _choice_criteria(question: DecisionQuestion) -> dict[str, Any]:
    if not question.choices:
        raise TypeSafeDecisionError(
            f"Choice question '{question.id}' requires at least one choice."
        )

    labels = [str(choice) for choice in question.choices]
    if len(set(labels)) != len(labels):
        raise TypeSafeDecisionError(
            f"Choice question '{question.id}' contains duplicate choice labels."
        )

    descriptions = question.metadata.get("criteria")
    if descriptions is None:
        return {label: None for label in labels}
    if not isinstance(descriptions, Mapping):
        raise TypeSafeDecisionError(
            f"Choice question '{question.id}' metadata.criteria must be a mapping."
        )
    return {label: descriptions.get(label) for label in labels}


def _score_criteria(question: DecisionQuestion) -> list[Any]:
    raw = question.metadata.get("criteria")
    if raw is not None and not isinstance(raw, (list, tuple)):
        raise TypeSafeDecisionError(
            f"Score question '{question.id}' metadata.criteria must be a list or tuple."
        )
    criteria = list(raw) if raw is not None else list(question.choices)
    if len(criteria) < 2:
        raise TypeSafeDecisionError(
            f"Score question '{question.id}' requires at least two ordered levels."
        )
    return criteria


def _translate_question(question: DecisionQuestion) -> dict[str, Any]:
    wire_type = _question_wire_type(question.kind)
    payload: dict[str, Any] = {
        "type": wire_type,
        "instructions": question.instruction,
    }

    if question.kind == DecisionKind.BOOLEAN:
        criteria = _boolean_criteria(question)
        if criteria is not None:
            payload["criteria"] = criteria
    elif question.kind == DecisionKind.CHOICE:
        payload["criteria"] = _choice_criteria(question)
    elif question.kind == DecisionKind.SCORE:
        payload["criteria"] = _score_criteria(question)

    return payload


def _translate_answer(
    question: DecisionQuestion,
    payload: Any,
) -> DecisionAnswer:
    if not isinstance(payload, Mapping):
        raise TypeSafeDecisionError(
            f"TypeSafe answer for '{question.id}' is not an object."
        )

    answer_type = str(payload.get("type") or "")
    expected_type = _question_wire_type(question.kind)
    if answer_type != expected_type:
        raise TypeSafeDecisionError(
            f"TypeSafe answer for '{question.id}' has type '{answer_type}', "
            f"expected '{expected_type}'."
        )

    if question.kind == DecisionKind.BOOLEAN:
        try:
            probability_true = float(payload["noul"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TypeSafeDecisionError(
                f"TypeSafe noul answer for '{question.id}' is missing a valid "
                "probability."
            ) from exc
        if not 0.0 <= probability_true <= 1.0:
            raise TypeSafeDecisionError(
                f"TypeSafe noul answer for '{question.id}' is outside [0, 1]."
            )
        value = probability_true >= 0.5
        confidence = probability_true if value else 1.0 - probability_true
        return DecisionAnswer(
            value=value,
            confidence=confidence,
            calibrated=True,
            metadata={
                "type": "noul",
                "probability_true": probability_true,
            },
        )

    if question.kind == DecisionKind.CHOICE:
        value = payload.get("choice")
        if value is None:
            raise TypeSafeDecisionError(
                f"TypeSafe choice answer for '{question.id}' is missing 'choice'."
            )
        allowed = {str(choice) for choice in question.choices}
        if str(value) not in allowed:
            raise TypeSafeDecisionError(
                f"TypeSafe choice answer for '{question.id}' returned "
                f"unrecognized choice '{value}'."
            )
        probabilities = payload.get("probabilities")
        if not isinstance(probabilities, Mapping):
            raise TypeSafeDecisionError(
                f"TypeSafe choice answer for '{question.id}' is missing "
                "probabilities."
            )
        try:
            provider_confidence = float(payload["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TypeSafeDecisionError(
                f"TypeSafe choice answer for '{question.id}' is missing a valid "
                "confidence."
            ) from exc
        if not 0.0 <= provider_confidence <= 1.0:
            raise TypeSafeDecisionError(
                f"TypeSafe choice confidence for '{question.id}' is outside [0, 1]."
            )
        try:
            answer_probability = float(probabilities[str(value)])
        except (KeyError, TypeError, ValueError) as exc:
            raise TypeSafeDecisionError(
                f"TypeSafe choice answer for '{question.id}' is missing the "
                "selected choice probability."
            ) from exc
        if not 0.0 <= answer_probability <= 1.0:
            raise TypeSafeDecisionError(
                f"TypeSafe choice probability for '{question.id}' is outside [0, 1]."
            )
        return DecisionAnswer(
            value=value,
            confidence=answer_probability,
            calibrated=True,
            metadata={
                "type": "choice",
                "probabilities": dict(probabilities),
                "provider_confidence": provider_confidence,
            },
        )

    try:
        score = float(payload["score"])
        confidence = float(payload["confidence"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TypeSafeDecisionError(
            f"TypeSafe score answer for '{question.id}' is missing a valid "
            "score/confidence."
        ) from exc
    if not 0.0 <= confidence <= 1.0:
        raise TypeSafeDecisionError(
            f"TypeSafe score confidence for '{question.id}' is outside [0, 1]."
        )
    criteria = _score_criteria(question)
    if not 0.0 <= score <= float(len(criteria) - 1):
        raise TypeSafeDecisionError(
            f"TypeSafe score answer for '{question.id}' is outside the requested "
            "rubric range."
        )
    probabilities = payload.get("probabilities")
    legend = payload.get("legend")
    if not isinstance(probabilities, Mapping) or not isinstance(legend, Mapping):
        raise TypeSafeDecisionError(
            f"TypeSafe score answer for '{question.id}' is missing "
            "probabilities/legend."
        )
    return DecisionAnswer(
        value=score,
        confidence=confidence,
        calibrated=False,
        metadata={
            "type": "score",
            "probabilities": dict(probabilities),
            "legend": dict(legend),
            "provider_confidence": confidence,
        },
    )


class TypeSafeDecisionProvider:
    """Decision provider backed by TypeSafe's System One HTTP API."""

    def __init__(
        self,
        *,
        settings: DecisionSettings,
        environ: Mapping[str, str] | None = None,
        client: Any = None,
    ) -> None:
        if settings.provider != "typesafe":
            raise TypeSafeDecisionConfigurationError(
                "TypeSafeDecisionProvider requires provider='typesafe'."
            )

        self._settings = settings
        self._config = TypeSafeDecisionConfig.from_environment(environ)
        self._owns_client = client is None
        if client is not None:
            self._client = client
        else:
            self._client = make_httpx_client() or httpx.Client(timeout=30.0)
        self._closed = False

    @property
    def name(self) -> str:
        return "typesafe"

    @property
    def model(self) -> str:
        return self._config.model

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if self._closed:
            raise TypeSafeDecisionError("TypeSafe decision provider is closed.")
        if not request.questions:
            raise TypeSafeDecisionError(
                "Decision request requires at least one question."
            )
        if not isinstance(request.state, (str, dict, list)):
            raise TypeSafeDecisionError(
                "TypeSafe decision state must be a string, mapping, or list."
            )

        question_ids = [question.id for question in request.questions]
        if len(set(question_ids)) != len(question_ids):
            raise TypeSafeDecisionError(
                "Decision request contains duplicate question ids."
            )
        questions = {
            question.id: _translate_question(question) for question in request.questions
        }
        payload = {
            "state": request.state,
            "model": self._config.model,
            "questions": questions,
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        try:
            response = self._client.post(
                _system_one_url(self._config.base_url),
                headers=headers,
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise TypeSafeDecisionError(
                f"TypeSafe decision request failed: {type(exc).__name__}."
            ) from exc

        status_code = int(getattr(response, "status_code", 0) or 0)
        if not 200 <= status_code < 300:
            detail = _safe_response_error_detail(
                response,
                secrets=(self._config.api_key,),
            )
            suffix = f": {detail}" if detail else "."
            raise TypeSafeDecisionError(
                f"TypeSafe decision request failed with HTTP {status_code}{suffix}"
            )

        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise TypeSafeDecisionError(
                "TypeSafe decision response was not valid JSON."
            ) from exc
        if not isinstance(data, Mapping):
            raise TypeSafeDecisionError("TypeSafe decision response is not an object.")

        raw_answers = data.get("answers")
        if not isinstance(raw_answers, Mapping):
            raise TypeSafeDecisionError(
                "TypeSafe decision response is missing an answers object."
            )

        answers: dict[str, DecisionAnswer] = {}
        for question in request.questions:
            if question.id not in raw_answers:
                raise TypeSafeDecisionError(
                    f"TypeSafe decision response is missing answer '{question.id}'."
                )
            answers[question.id] = _translate_answer(
                question,
                raw_answers[question.id],
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        response_model = str(data.get("model") or self._config.model)
        return DecisionResult(
            provider="typesafe",
            model=response_model,
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

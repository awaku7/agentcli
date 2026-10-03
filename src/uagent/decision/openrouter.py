"""OpenRouter Decisions API adapter for structured decision models."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..auth.credential_store import get_default_credential_store
from ..auth.provider_credentials import get_provider_api_key
from ..providers.util_providers import make_httpx_client
from .models import DecisionAnswer, DecisionRequest, DecisionResult
from .settings import DecisionSettings
from .typesafe import (
    TypeSafeDecisionError,
    _safe_response_error_detail,
    _translate_answer,
    _translate_question,
)


class OpenRouterDecisionError(RuntimeError):
    """Base error raised by the OpenRouter decision adapter."""


class OpenRouterDecisionConfigurationError(OpenRouterDecisionError):
    """Raised when active OpenRouter decision configuration is incomplete."""


@dataclass(frozen=True)
class OpenRouterDecisionConfig:
    """Resolved OpenRouter Decisions API configuration."""

    model: str = "~typesafe/jev-latest"
    base_url: str = "https://openrouter.ai/api"
    api_key: str = field(default="", repr=False)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "OpenRouterDecisionConfig":
        env = os.environ if environ is None else environ
        model = (
            str(
                env.get("UAGENT_DECISION_OPENROUTER_DEPNAME") or "~typesafe/jev-latest"
            ).strip()
            or "~typesafe/jev-latest"
        )
        base_url = (
            str(
                env.get("UAGENT_DECISION_OPENROUTER_BASE_URL")
                or "https://openrouter.ai/api"
            ).strip()
            or "https://openrouter.ai/api"
        )
        api_key = str(env.get("UAGENT_DECISION_OPENROUTER_API_KEY") or "").strip()
        if not api_key:
            store = None
            if environ is None:
                try:
                    store = get_default_credential_store()
                except Exception:
                    store = None
            api_key = str(
                get_provider_api_key("openrouter", store=store, environ=env) or ""
            ).strip()
        if not api_key:
            raise OpenRouterDecisionConfigurationError(
                "OpenRouter Decision Provider requires "
                "UAGENT_DECISION_OPENROUTER_API_KEY, a stored OpenRouter credential, "
                "UAGENT_OPENROUTER_API_KEY, or OPENROUTER_API_KEY."
            )
        return cls(model=model, base_url=base_url.rstrip("/"), api_key=api_key)


def _decisions_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/decisions"):
        return normalized
    if normalized.endswith("/api/v1"):
        normalized = normalized[: -len("/v1")]
    if normalized.endswith("/alpha"):
        return normalized + "/decisions"
    return normalized + "/alpha/decisions"


def _translate_questions(request: DecisionRequest) -> dict[str, dict[str, Any]]:
    try:
        return {
            question.id: _translate_question(question) for question in request.questions
        }
    except TypeSafeDecisionError as exc:
        raise OpenRouterDecisionError(
            str(exc).replace("TypeSafe", "OpenRouter")
        ) from exc


def _translate_result_answer(question: Any, payload: Any) -> DecisionAnswer:
    try:
        return _translate_answer(question, payload)
    except TypeSafeDecisionError as exc:
        raise OpenRouterDecisionError(
            str(exc).replace("TypeSafe", "OpenRouter")
        ) from exc


class OpenRouterDecisionProvider:
    """Decision provider backed by OpenRouter's Decisions API."""

    def __init__(
        self,
        *,
        settings: DecisionSettings,
        environ: Mapping[str, str] | None = None,
        client: Any = None,
    ) -> None:
        if settings.provider != "openrouter":
            raise OpenRouterDecisionConfigurationError(
                "OpenRouterDecisionProvider requires provider='openrouter'."
            )

        self._settings = settings
        self._config = OpenRouterDecisionConfig.from_environment(environ)
        self._owns_client = client is None
        if client is not None:
            self._client = client
        else:
            self._client = make_httpx_client() or httpx.Client(timeout=30.0)
        self._closed = False

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return self._config.model

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if self._closed:
            raise OpenRouterDecisionError("OpenRouter decision provider is closed.")
        if not request.questions:
            raise OpenRouterDecisionError(
                "Decision request requires at least one question."
            )
        if not isinstance(request.state, (str, dict, list)):
            raise OpenRouterDecisionError(
                "OpenRouter decision state must be a string, mapping, or list."
            )

        question_ids = [question.id for question in request.questions]
        if len(set(question_ids)) != len(question_ids):
            raise OpenRouterDecisionError(
                "Decision request contains duplicate question ids."
            )

        payload = {
            "state": request.state,
            "model": self._config.model,
            "questions": _translate_questions(request),
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
            raise OpenRouterDecisionError(
                f"OpenRouter decision request failed: {type(exc).__name__}."
            ) from exc

        status_code = int(getattr(response, "status_code", 0) or 0)
        if not 200 <= status_code < 300:
            detail = _safe_response_error_detail(
                response,
                secrets=(self._config.api_key,),
            )
            suffix = f": {detail}" if detail else "."
            raise OpenRouterDecisionError(
                f"OpenRouter decision request failed with HTTP {status_code}{suffix}"
            )

        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise OpenRouterDecisionError(
                "OpenRouter decision response was not valid JSON."
            ) from exc
        if not isinstance(data, Mapping):
            raise OpenRouterDecisionError(
                "OpenRouter decision response is not an object."
            )

        raw_answers = data.get("answers")
        if not isinstance(raw_answers, Mapping):
            raise OpenRouterDecisionError(
                "OpenRouter decision response is missing an answers object."
            )

        answers: dict[str, DecisionAnswer] = {}
        for question in request.questions:
            if question.id not in raw_answers:
                raise OpenRouterDecisionError(
                    f"OpenRouter decision response is missing answer '{question.id}'."
                )
            answers[question.id] = _translate_result_answer(
                question,
                raw_answers[question.id],
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        response_model = str(data.get("model") or self._config.model)
        return DecisionResult(
            provider="openrouter",
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

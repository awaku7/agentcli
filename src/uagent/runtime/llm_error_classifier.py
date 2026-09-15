"""Classify provider failures before retry policy makes a decision.

Adapters may supply structured HTTP metadata; the classifier retains a narrow
text fallback for legacy SDK exceptions during migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .round_runtime import RetryReason, RetryRequest

ErrorKind = Literal[
    "context_overflow",
    "stale_continuation",
    "unsupported_feature",
    "transport",
    "unknown",
]


@dataclass(frozen=True)
class LLMErrorClassification:
    kind: ErrorKind
    status_code: int | None
    error_type: str
    headers: dict[str, str]
    detail: str

    def retry_request(self) -> RetryRequest | None:
        reason: RetryReason | None = {
            "context_overflow": "context_overflow",
            "stale_continuation": "stale_continuation",
            "unsupported_feature": "feature_fallback",
            "transport": "transport",
        }.get(self.kind)
        return RetryRequest(reason, self.detail) if reason is not None else None


class LLMErrorClassifier:
    """Provider-agnostic error classification with safe metadata extraction."""

    def classify(self, error: BaseException) -> LLMErrorClassification:
        status = self._status_code(error)
        headers = self._headers(error)
        detail = self._detail(error)
        lowered = detail.lower()
        kind: ErrorKind
        if self._is_context_overflow(lowered):
            kind = "context_overflow"
        elif self._is_stale_continuation(lowered):
            kind = "stale_continuation"
        elif self._is_unsupported_feature(lowered):
            kind = "unsupported_feature"
        elif self._is_transport(error, status, lowered):
            kind = "transport"
        else:
            kind = "unknown"
        return LLMErrorClassification(
            kind=kind,
            status_code=status,
            error_type=type(error).__name__,
            headers=headers,
            detail=detail[:800],
        )

    @staticmethod
    def _status_code(error: BaseException) -> int | None:
        value = getattr(error, "status_code", None) or getattr(error, "status", None)
        if value is None:
            response = getattr(error, "response", None)
            value = getattr(response, "status_code", None) or getattr(response, "status", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _headers(error: BaseException) -> dict[str, str]:
        result: dict[str, str] = {}
        for source in (getattr(error, "headers", None), getattr(getattr(error, "response", None), "headers", None)):
            if not source:
                continue
            try:
                items = source.items()
            except AttributeError:
                continue
            for key, value in items:
                result[str(key).lower()] = str(value)
        return result

    @staticmethod
    def _detail(error: BaseException) -> str:
        parts = [str(error)]
        body = getattr(error, "body", None)
        if body is not None:
            parts.append(str(body))
        response = getattr(error, "response", None)
        text = getattr(response, "text", None)
        if text:
            parts.append(str(text))
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _is_context_overflow(text: str) -> bool:
        return (
            "input token count exceeds" in text
            or "maximum number of tokens allowed" in text
            or ("context window" in text and ("exceed" in text or "maximum" in text))
        )

    @staticmethod
    def _is_stale_continuation(text: str) -> bool:
        return any(
            marker in text
            for marker in (
                "previous_response_id",
                "no tool call found",
                "no tool output found",
                "referenced response not found",
                "response not found or expired",
            )
        )

    @staticmethod
    def _is_unsupported_feature(text: str) -> bool:
        return any(
            marker in text
            for marker in (
                "does not support tools",
                "does not support thinking",
                "reasoning.effort",
                "unsupported feature",
            )
        )

    @staticmethod
    def _is_transport(error: BaseException, status: int | None, text: str) -> bool:
        if isinstance(error, (TimeoutError, ConnectionError)):
            return True
        if status == 429 or status is not None and 500 <= status <= 599:
            return True
        return any(
            marker in text
            for marker in (
                "rate limit",
                "too many requests",
                "connection error",
                "service unavailable",
                "gateway timeout",
            )
        )

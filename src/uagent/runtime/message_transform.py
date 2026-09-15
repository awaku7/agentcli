"""Semantic message transforms applied before provider projection.

This boundary owns transformations whose meaning is independent of the target
SDK. Provider message shape, request options, and HTTP serialization remain
outside it.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from ..util_common import strip_surrogates

TextTranslator = Callable[[str], str]


@dataclass(frozen=True)
class TransformResult:
    messages: tuple[Mapping[str, Any], ...]
    applied: tuple[str, ...]


def _normalize_text(value: Any) -> Any:
    if isinstance(value, str):
        return strip_surrogates(value)
    if isinstance(value, list):
        return [_normalize_text(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_text(item) for item in value)
    if isinstance(value, dict):
        return {
            _normalize_text(key) if isinstance(key, str) else key: _normalize_text(item)
            for key, item in value.items()
        }
    return value


class MessageTransformPipeline:
    """Apply provider-neutral semantic transforms without mutating history."""

    def apply(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        translator: TextTranslator | None = None,
    ) -> TransformResult:
        transformed = _normalize_text(copy.deepcopy(list(messages)))
        applied = ["surrogate_normalization"]
        if translator is not None:
            for message in transformed:
                if not isinstance(message, dict):
                    continue
                if message.get("role") not in {"system", "user", "assistant"}:
                    continue
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    message["content"] = translator(content)
            applied.append("translation")
        return TransformResult(tuple(transformed), tuple(applied))

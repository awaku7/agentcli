"""Lazily imported provider SDK symbols.

Importing the OpenAI and Google Gen AI SDKs takes seconds because they build
large pydantic model hierarchies at import time. Only the OpenAI exception
classes and the Gemini ``types`` module are needed, and only from error paths
or provider-specific code, so both are resolved on first use instead of while
this package is being imported.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=None)
def _openai_exception(name: str) -> type[BaseException] | None:
    """Return one OpenAI exception class, or None when openai is unavailable."""
    try:
        import openai
    except Exception:
        return None
    value = getattr(openai, name, None)
    return value if isinstance(value, type) else None


def is_openai_error(exc: BaseException | None, *names: str) -> bool:
    """Whether ``exc`` is an instance of any named OpenAI exception class.

    Returns False when openai is not installed, which matches the previous
    ``BadRequestError is not None and isinstance(...)`` guards.
    """
    if exc is None or not names:
        return False
    for name in names:
        error_type = _openai_exception(name)
        if error_type is not None and isinstance(exc, error_type):
            return True
    return False


@lru_cache(maxsize=None)
def gemini_types() -> Any | None:
    """Return ``google.genai.types``, or None when the SDK is unavailable."""
    try:
        from google.genai import types
    except Exception:
        return None
    return types

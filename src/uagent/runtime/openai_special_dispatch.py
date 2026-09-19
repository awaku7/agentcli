"""Compatibility dispatch for special OpenAI-compatible fallbacks."""

from __future__ import annotations

from typing import Any

from .legacy_special_provider_fallback import (
    LEGACY_OPENAI_SPECIAL_HANDLERS as _SPECIAL_OPENAI_HANDLERS,
)


def call_special_openai_round(*, provider: str, **kwargs: Any) -> Any | None:
    """Call a provider-specific legacy fallback when registry routing is off."""
    handler = _SPECIAL_OPENAI_HANDLERS.get((provider or "").strip().lower())
    if handler is None:
        return None
    return handler(**kwargs)


__all__ = ["call_special_openai_round"]

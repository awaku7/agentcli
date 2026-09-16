"""Compatibility dispatch tables for provider-family round helpers.

The provider-specific request implementations remain in ``llm_round_helpers``
while this module owns only the selection of an already-normalized caller.
"""

from __future__ import annotations

from typing import Any

from ..llm_round_helpers import (
    _call_claude_round,
    _call_gemini_round,
    _call_novita_round,
    _call_together_round,
    _call_vercel_round,
    _call_zai_round,
)

_LEGACY_REASONING_ROUND_CALLERS = {
    "zai": _call_zai_round,
    "vercel": _call_vercel_round,
    "together": _call_together_round,
    "novita": _call_novita_round,
}

_LEGACY_GEMINI_ROUND_CALLERS = {
    "gemini": _call_gemini_round,
    "vertexai": _call_gemini_round,
}


def call_legacy_gemini_round(*, provider: str, **kwargs: Any) -> Any:
    """Dispatch Gemini-family rounds through the compatibility registry."""
    try:
        caller = _LEGACY_GEMINI_ROUND_CALLERS[(provider or "").strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported Gemini provider: {provider}") from exc
    return caller(**kwargs)


def call_legacy_claude_round(**kwargs: Any) -> Any:
    """Dispatch Claude rounds through the compatibility registry."""
    return _call_claude_round(**kwargs)


def call_legacy_reasoning_round(*, provider: str, **kwargs: Any) -> Any:
    """Dispatch shared reasoning-provider rounds through one registry."""
    try:
        caller = _LEGACY_REASONING_ROUND_CALLERS[(provider or "").strip().lower()]
    except KeyError as exc:
        raise ValueError(
            f"unsupported legacy reasoning provider: {provider}"
        ) from exc
    return caller(**kwargs)


__all__ = [
    "call_legacy_claude_round",
    "call_legacy_gemini_round",
    "call_legacy_reasoning_round",
]

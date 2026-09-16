"""Provider registry for the remaining legacy round handlers."""

from __future__ import annotations

from typing import Any

from .legacy_claude_round import run_legacy_claude_round
from .legacy_deepseek_round import run_legacy_deepseek_round
from .legacy_gateway_round import run_legacy_gateway_round
from .legacy_gemini_round import run_legacy_gemini_round
from .legacy_zai_round import run_legacy_zai_round

_LEGACY_ROUND_HANDLERS = {
    "gemini": run_legacy_gemini_round,
    "vertexai": run_legacy_gemini_round,
    "claude": run_legacy_claude_round,
    "deepseek": run_legacy_deepseek_round,
    "mimo": run_legacy_deepseek_round,
    "zai": run_legacy_zai_round,
    "novita": run_legacy_zai_round,
    "vercel": run_legacy_gateway_round,
    "together": run_legacy_gateway_round,
}


def run_legacy_provider_round(
    *, provider: str, **kwargs: Any
) -> tuple[str, Any, str | None, int, str] | None:
    """Run a registered legacy provider handler, or return ``None``."""
    handler = _LEGACY_ROUND_HANDLERS.get((provider or "").strip().lower())
    if handler is None:
        return None
    return handler(provider=provider, **kwargs)


__all__ = ["run_legacy_provider_round"]

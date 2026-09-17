"""Provider registry for the remaining legacy round handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

LegacyRoundResult: TypeAlias = tuple[str, Any, str | None, int, str]


@dataclass(frozen=True)
class LegacyRoundOutcome:
    """Provider-neutral metadata around an unchanged legacy round result."""

    provider: str
    status: str
    assistant_text: str
    raw_result: LegacyRoundResult


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
) -> LegacyRoundResult | None:
    """Run a registered legacy provider handler, or return ``None``."""
    handler = _LEGACY_ROUND_HANDLERS.get((provider or "").strip().lower())
    if handler is None:
        return None
    return handler(provider=provider, **kwargs)


def run_legacy_provider_outcome(
    *, provider: str, **kwargs: Any
) -> LegacyRoundOutcome | None:
    """Wrap a legacy tuple without changing its compatibility payload."""
    result = run_legacy_provider_round(provider=provider, **kwargs)
    if result is None:
        return None
    return LegacyRoundOutcome(
        provider=(provider or "").strip().lower(),
        status=str(result[0]),
        assistant_text=str(result[4] or ""),
        raw_result=result,
    )


__all__ = [
    "LegacyRoundOutcome",
    "LegacyRoundResult",
    "run_legacy_provider_outcome",
    "run_legacy_provider_round",
]

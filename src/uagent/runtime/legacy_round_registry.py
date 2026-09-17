"""Provider registry for the remaining legacy round handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, TypeAlias

LegacyRoundResult: TypeAlias = tuple[Any, ...]


@dataclass(frozen=True)
class RoundOutcomeCapabilities:
    """Execution capabilities used after provider dispatch."""

    handles_collected_result: bool = False
    owns_tool_execution: bool = False
    host_rendered: bool = False


@dataclass(frozen=True)
class LegacyRoundOutcome:
    """Provider-neutral metadata around an unchanged legacy round result."""

    provider: str
    status: str
    assistant_text: str
    raw_result: LegacyRoundResult
    client: Any = None
    reasoning_text: str = ""
    tool_calls: tuple[Mapping[str, Any], ...] = ()
    is_xai_grpc: bool = False
    capabilities: RoundOutcomeCapabilities = RoundOutcomeCapabilities()
    flow: Literal["registry", "legacy", "openai_compatible"] = "legacy"


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
        client=result[1] if len(result) > 1 else None,
        capabilities=RoundOutcomeCapabilities(
            owns_tool_execution=True,
            host_rendered=True,
        ),
    )


__all__ = [
    "LegacyRoundOutcome",
    "LegacyRoundResult",
    "RoundOutcomeCapabilities",
    "run_legacy_provider_outcome",
    "run_legacy_provider_round",
]

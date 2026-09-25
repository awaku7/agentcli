"""Provider registry for the remaining legacy round handlers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal, Mapping, TypeAlias

from .round_contracts import RoundSummary

LegacyRoundResult: TypeAlias = tuple[Any, ...]


@dataclass(frozen=True)
class RoundOutcomeCapabilities:
    """Execution capabilities used after provider dispatch."""

    handles_collected_result: bool = False
    owns_tool_execution: bool = False
    host_rendered: bool = False
    supports_tool_continuation: bool = False


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
    summary: RoundSummary | None = None


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


def _summary_status_for_action(action: str) -> str:
    normalized = (action or "").strip().lower()
    if normalized == "return":
        return "failed"
    if normalized == "break":
        return "interrupted"
    if normalized == "continue":
        return "continue"
    return "completed"


def run_legacy_provider_outcome(
    *, provider: str, **kwargs: Any
) -> LegacyRoundOutcome | None:
    """Wrap a legacy tuple without changing its compatibility payload.

    Provider-call tracing is owned by ``legacy_provider_dispatch`` so handler
    post-processing and tool execution stay outside the canonical ``chat`` span.
    """

    normalized_provider = (provider or "").strip().lower()
    handler = _LEGACY_ROUND_HANDLERS.get(normalized_provider)
    if handler is None:
        return None

    started = time.perf_counter()
    result = handler(provider=provider, **kwargs)
    assistant_text = str(result[4] or "") if len(result) > 4 else ""
    action = str(result[0] or "").strip().lower() if result else ""
    summary = RoundSummary(
        status=_summary_status_for_action(action),
        duration_ms=(time.perf_counter() - started) * 1000.0,
        assistant_chars=len(assistant_text),
    )
    return LegacyRoundOutcome(
        provider=normalized_provider,
        status=action,
        assistant_text=assistant_text,
        raw_result=result,
        client=result[1] if len(result) > 1 else None,
        capabilities=RoundOutcomeCapabilities(
            owns_tool_execution=True,
            host_rendered=True,
        ),
        summary=summary,
    )


__all__ = [
    "LegacyRoundOutcome",
    "LegacyRoundResult",
    "RoundOutcomeCapabilities",
    "run_legacy_provider_outcome",
    "run_legacy_provider_round",
]

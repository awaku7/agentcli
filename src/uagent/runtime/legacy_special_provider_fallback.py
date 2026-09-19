"""Compatibility boundary for special providers not yet fully removed.

PFN and Grok now have registry runtimes. This module contains only the
explicit legacy fallback used when registry routing is disabled or unavailable;
normal dispatch should never need to know their SDK-specific entry points.
"""

from __future__ import annotations

from typing import Any

from ..llm_grok_round import _call_grok_round
from ..providers.llm_pfn import pfn_chat_with_tools

LEGACY_OPENAI_SPECIAL_HANDLERS = {"pfn": pfn_chat_with_tools}


def call_legacy_special_openai_round(*, provider: str, **kwargs: Any) -> Any | None:
    """Call a PFN-compatible legacy fallback, or return ``None``."""
    handler = LEGACY_OPENAI_SPECIAL_HANDLERS.get((provider or "").strip().lower())
    if handler is None:
        return None
    return handler(**kwargs)


def call_legacy_grok_grpc_round(
    *, provider: str, client: Any, **kwargs: Any
) -> Any | None:
    """Call the Grok SDK fallback only when the client is xAI's gRPC client."""
    if (provider or "").strip().lower() != "grok":
        return None
    try:
        from xai_sdk import Client as _XAIClient

        if not isinstance(client, _XAIClient):
            return None
    except Exception:
        return None
    ok, new_client, assistant_text, tool_calls = _call_grok_round(
        provider=provider,
        client=client,
        **kwargs,
    )
    return ok, new_client, assistant_text, "", tool_calls, True


__all__ = [
    "LEGACY_OPENAI_SPECIAL_HANDLERS",
    "call_legacy_grok_grpc_round",
    "call_legacy_special_openai_round",
]

"""Special handlers for OpenAI-compatible provider families."""

from __future__ import annotations

from typing import Any

from ..providers.llm_pfn import pfn_chat_with_tools

_SPECIAL_OPENAI_HANDLERS = {"pfn": pfn_chat_with_tools}


def call_special_openai_round(*, provider: str, **kwargs: Any) -> Any | None:
    """Call a provider-specific OpenAI-compatible handler when registered."""
    handler = _SPECIAL_OPENAI_HANDLERS.get((provider or "").strip().lower())
    if handler is None:
        return None
    return handler(**kwargs)


__all__ = ["call_special_openai_round"]

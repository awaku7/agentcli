"""LM Studio transport dispatcher.

The concrete Chat Completions and Responses implementations intentionally live
in separate modules. This module keeps the compatibility surface used by the
rest of uagent and provides the opt-in transport dispatch point.
"""

from __future__ import annotations

from typing import Any

from .llm_lmstudio_chat import make_client
from .llm_lmstudio_chat import prepare_kwargs as prepare_chat_kwargs
from .llm_lmstudio_responses import endpoint_available
from .llm_lmstudio_responses import prepare_kwargs as prepare_responses_kwargs


def make_lmstudio_client(core: Any) -> Any:
    """Backward-compatible alias for the LM Studio client factory."""
    return make_client(core)


def responses_endpoint_available(core: Any = None, *, timeout: float = 2.0) -> bool:
    """Backward-compatible alias for the Responses endpoint probe."""
    return endpoint_available(core, timeout=timeout)


def apply_lmstudio_transport(kwargs: dict[str, Any], *, responses: bool) -> None:
    """Normalize a request for exactly one LM Studio transport."""
    kwargs["_lmstudio_transport"] = "responses" if responses else "chat"
    if responses:
        prepare_responses_kwargs(kwargs)
    else:
        prepare_chat_kwargs(kwargs)


__all__ = [
    "apply_lmstudio_transport",
    "make_lmstudio_client",
    "responses_endpoint_available",
]

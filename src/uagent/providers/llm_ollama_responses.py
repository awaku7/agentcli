from __future__ import annotations

from typing import Any

from .llm_ollama import _ollama_extra_params


def apply_ollama_responses_compat(
    resp_kwargs: dict[str, Any],
    *,
    provider: str,
    depname: str,
) -> None:
    """Apply Ollama-specific Responses API request options."""

    if provider != "ollama":
        return

    try:
        extra_body = resp_kwargs.get("extra_body")
        if not isinstance(extra_body, dict):
            extra_body = {}
        extra_body.update(_ollama_extra_params())
        resp_kwargs["extra_body"] = extra_body
    except Exception:
        pass

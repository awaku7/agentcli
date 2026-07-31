from __future__ import annotations

from typing import Any

from .llm_ollama import _ollama_extra_params, _resolve_ollama_max_tokens


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

        # The Responses API uses the top-level ``max_output_tokens`` field.
        # When no explicit limit was already set, fall back to llmcapa's
        # max_output_tokens instead of a hardcoded default.
        if "max_output_tokens" not in resp_kwargs:
            limit = _resolve_ollama_max_tokens(depname)
            if limit:
                resp_kwargs["max_output_tokens"] = limit
    except Exception:
        pass

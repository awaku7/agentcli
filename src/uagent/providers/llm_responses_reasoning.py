"""Helpers for requesting reasoning summaries from Responses API providers."""

from __future__ import annotations

import sys
from typing import Any

from ..env_utils import env_get

_SUMMARY_PROVIDERS = {"meta", "openai", "azure"}


def apply_responses_reasoning_summary(
    resp_kwargs: dict[str, Any], *, provider: str
) -> None:
    """Request an automatic reasoning summary when reasoning is configured.

    OpenAI and Azure OpenAI expose reasoning summaries through
    ``reasoning.summary``. Meta's Responses API uses the same request shape.
    Don't add the field without an effort value: support for summary-only
    requests is not consistent across providers/deployments.
    """
    if (provider or "").strip().lower() not in _SUMMARY_PROVIDERS:
        return
    reasoning = resp_kwargs.get("reasoning")
    if not isinstance(reasoning, dict) or "effort" not in reasoning:
        return

    try:
        from ..util_tools import get_display_reasoning

        if not get_display_reasoning():
            return
    except Exception:
        # Preserve the historical best-effort behavior when display settings
        # cannot be queried.
        pass

    reasoning.setdefault("summary", "auto")
    debug = (env_get("UAGENT_RESPONSES_REASONING_DEBUG", "") or "").strip().lower()
    if debug in {"1", "true", "yes", "on"}:
        print(
            "[Responses debug] request: "
            f"provider={(provider or '').strip().lower()} "
            f"effort={reasoning.get('effort')} summary={reasoning.get('summary')}",
            file=sys.stderr,
            flush=True,
        )

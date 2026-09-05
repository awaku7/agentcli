"""Meta Model API Responses compatibility helpers."""

from __future__ import annotations

from typing import Any


def apply_meta_responses_reasoning_summary(
    resp_kwargs: dict[str, Any], *, provider: str
) -> None:
    """Request a reasoning summary for Meta (Responses API).

    Meta keeps the raw chain-of-thought private. A human-readable summary
    (``summary_text``) is returned only when ``reasoning.summary`` is
    requested. Without this, the parse side never sees ``summary_text`` and
    ``[Meta Reasoning]`` is never displayed.

    No-op unless ``provider == "meta"`` and ``reasoning.effort`` is present.
    Summary-only without effort is intentionally not sent: validity without
    effort is undocumented and a 400 here would break previously-working
    calls (e.g. ``UAGENT_REASONING=off`` / auto-non-thinking).
    """
    if (provider or "").strip().lower() != "meta":
        return
    reasoning = resp_kwargs.get("reasoning")
    if not isinstance(reasoning, dict):
        return
    if "effort" not in reasoning:
        return
    try:
        from ..util_tools import get_display_reasoning as _gdr

        _show = bool(_gdr())
    except Exception:
        _show = True
    if not _show:
        return
    try:
        reasoning["summary"] = "auto"
    except Exception:
        pass

"""Meta Model API Responses compatibility helpers."""

from __future__ import annotations

from typing import Any


def apply_meta_responses_compat(
    resp_kwargs: dict[str, Any], *, provider: str, depname: str
) -> None:
    """Remove Responses parameters unsupported by the Meta Model API."""
    del depname  # Reserved for future model-specific compatibility.
    if (provider or "").strip().lower() != "meta":
        return
    # Meta documents client-managed compaction; context_management is an
    # OpenAI-specific request option and must not be sent to Meta.
    resp_kwargs.pop("context_management", None)

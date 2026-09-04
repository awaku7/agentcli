"""Meta Model API Responses compatibility helpers."""

from __future__ import annotations

from typing import Any


def apply_meta_responses_compat(
    resp_kwargs: dict[str, Any], *, provider: str, depname: str
) -> None:
    """Remove Responses parameters not supported by Meta Model API.

    Meta supports the Responses API and server-managed ``previous_response_id``
    continuation, but conversation compaction is client-managed.  Therefore
    OpenAI's ``context_management`` request parameter must not be sent.
    """
    del depname  # Reserved for model-specific compatibility in the future.
    if provider != "meta":
        return
    resp_kwargs.pop("context_management", None)

"""Gemini API transport selection shared by Gemini and Vertex AI."""

from __future__ import annotations

from ..env_utils import env_get

_ENV_NAME = "UAGENT_GEMINI_API_MODE"
_MODE_ALIASES = {
    "generate_content": "generate_content",
    "generate-content": "generate_content",
    "generatecontent": "generate_content",
    "legacy": "generate_content",
    "interactions": "interactions",
    "interactions_api": "interactions",
    "interactions-api": "interactions",
}


def gemini_api_mode() -> str:
    """Return the configured Google model API transport.

    The existing GenerateContent transport remains the default. Set
    ``UAGENT_GEMINI_API_MODE=interactions`` to use the Interactions API for
    either the ``gemini`` or ``vertexai`` provider.
    """
    raw = (env_get(_ENV_NAME, "generate_content") or "generate_content").strip().lower()
    mode = _MODE_ALIASES.get(raw)
    if mode is None:
        raise ValueError(
            f"Invalid {_ENV_NAME}={raw!r}; expected 'generate_content' or 'interactions'."
        )
    return mode


__all__ = ["gemini_api_mode"]

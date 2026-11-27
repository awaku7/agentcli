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


def gemini_api_mode(model_name: str | None = None, provider: str | None = None) -> str:
    """Select the Google API transport, honoring an explicit environment override.

    Without an override, Interactions is selected when llmcapa positively
    identifies either the Interactions API or a feature that requires it
    (currently native tool search). Unknown models and unavailable capability
    data keep using the established GenerateContent API.
    """
    raw = (env_get(_ENV_NAME) or "").strip().lower()
    if raw:
        mode = _MODE_ALIASES.get(raw)
        if mode is None:
            raise ValueError(
                f"Invalid {_ENV_NAME}={raw!r}; expected 'generate_content' or 'interactions'."
            )
        return mode

    normalized_provider = (provider or "").strip().lower()
    normalized_model = (model_name or "").strip()
    if normalized_model and normalized_provider in {
        "gemini",
        "vertexai",
        "vertex-ai",
        "google",
    }:
        try:
            from ..llmcapa_util import get_capability, supports_feature

            for feature in ("interactions_api", "tool_search"):
                supported = supports_feature(
                    feature,
                    normalized_model,
                    normalized_provider,
                    default=None,
                )
                if supported is True:
                    return "interactions"
                if feature == "tool_search" and supported is None:
                    capability = get_capability(normalized_model, normalized_provider)
                    if getattr(capability, "supports_tool_search", None) is True:
                        return "interactions"
        except Exception:
            # llmcapa is optional; unknown capability must not change transport.
            pass
    return "generate_content"


__all__ = ["gemini_api_mode"]

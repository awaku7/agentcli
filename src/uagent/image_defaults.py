"""Shared defaults for image generation and editing models."""

from __future__ import annotations

DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2.6-flare"


def default_image_model(provider: str) -> str | None:
    """Return the provider's built-in image model, if one is defined."""
    provider = str(provider or "").strip().lower()
    defaults = {
        "openai": DEFAULT_OPENAI_IMAGE_MODEL,
        "gemini": "gemini-nano-banana-2.1",
        "vertexai": "gemini-nano-banana-2.1",
        "meta": "muse-image-1.0",
        "zai": "glm-image",
        "grok": "grok-imagine-image",
    }
    return defaults.get(provider)

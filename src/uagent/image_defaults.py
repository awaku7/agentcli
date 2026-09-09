"""Shared defaults for image generation and editing models."""

from __future__ import annotations

DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2.5-flare"


def default_image_model(provider: str) -> str | None:
    """Return the provider's built-in image model, if one is defined."""
    provider = str(provider or "").strip().lower()
    defaults = {
        "openai": DEFAULT_OPENAI_IMAGE_MODEL,
        "meta": "muse-image-1.0",
        "gemini": "imagen-4.0-generate-001",
        "vertexai": "imagen-4.0-generate-001",
        "zai": "glm-image",
        "grok": "grok-imagine-image",
    }
    return defaults.get(provider)

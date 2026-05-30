from __future__ import annotations

from .i18n import _

_IMAGE_DEFAULT_PROMPTS = {
    "describe": _(
        "Describe this screenshot and summarize the visible UI.",
        default="Describe this screenshot and summarize the visible UI.",
    ),
    "ocr": _(
        "Read all visible text in this screenshot and summarize it.",
        default="Read all visible text in this screenshot and summarize it.",
    ),
    "analyze": _(
        "Inspect this screenshot for errors, warnings, and important UI state.",
        default="Inspect this screenshot for errors, warnings, and important UI state.",
    ),
}


def build_image_default_prompt(kind: str = "describe") -> str:
    """Return a localized default prompt for image attachment workflows."""

    key = (kind or "describe").strip().lower()
    return _IMAGE_DEFAULT_PROMPTS.get(key, _IMAGE_DEFAULT_PROMPTS["describe"])

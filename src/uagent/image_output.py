"""Shared image output format helpers."""

from __future__ import annotations

from typing import Any

IMAGE_FORMATS = frozenset({"png", "jpeg", "webp"})


def normalize_output_format(value: Any) -> str:
    value = str(value or "png").strip().lower()
    return value if value in IMAGE_FORMATS else "png"


def image_extension(output_format: str) -> str:
    return "jpg" if output_format == "jpeg" else output_format


def image_mime(output_format: str) -> str:
    return "image/jpeg" if output_format == "jpeg" else f"image/{output_format}"

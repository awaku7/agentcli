"""Sanitize tool-result messages before durable history persistence."""

from __future__ import annotations

from typing import Any

_BINARY_KEY_MARKER = "[binary payload omitted from persisted history]"
_BINARY_KEYS = {
    "blob",
    "data_base64",
    "base64",
    "inline_data",
    "inlinedata",
    "pdf_b64",
    "audio_b64",
    "image_b64",
    "screenshot_data",
    "screenshotdata",
}


def _is_binary_key(key: Any) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in _BINARY_KEYS or "base64" in normalized


def _is_data_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return (
        value.strip().lower().startswith("data:") and ";base64," in value[:256].lower()
    )


def sanitize_binary_payload(value: Any) -> Any:
    """Return a copy with inline binary payloads replaced by bounded markers.

    This function is intentionally limited to binary-shaped fields. Ordinary
    Base64 used for authentication, signatures, protocol envelopes, or text is
    not removed unless it is explicitly stored under a binary field name.
    """
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_binary_key(key) or _is_data_url(item):
                result[key] = _BINARY_KEY_MARKER
            else:
                result[key] = sanitize_binary_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_binary_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_binary_payload(item) for item in value]
    return value


def sanitize_message_for_history(message: Any) -> Any:
    """Sanitize only tool messages, leaving user/assistant messages unchanged."""
    if not isinstance(message, dict) or str(message.get("role") or "") != "tool":
        return message
    return sanitize_binary_payload(message)


__all__ = [
    "sanitize_binary_payload",
    "sanitize_message_for_history",
]

"""Sanitize tool-result messages before durable history persistence."""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any

from ..utils.secret_mask import SECRET_MASK, _mask_inline_secrets, looks_like_secret_key

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
_PERSISTENCE_PUBLIC_RESULT_KEYS = frozenset(
    {"authorization_url", "signature", "token_id", "secret_findings", "has_token"}
)
_TOKEN_PUBLIC_METADATA_KEYS = frozenset({"token_id", "status", "expires_at"})


def _normalize_persistence_key(key: Any) -> str:
    return (
        re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
        .strip()
        .replace("-", "_")
        .lower()
    )


def _is_persistent_secret_key(key: Any) -> bool:
    """Classify persisted result keys without hiding known public result fields."""
    normalized = _normalize_persistence_key(key)
    if normalized in _PERSISTENCE_PUBLIC_RESULT_KEYS:
        return False
    return looks_like_secret_key(normalized)


def _is_binary_key(key: Any, value: Any = None) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    if normalized in _BINARY_KEYS:
        return True
    if "base64" not in normalized or not isinstance(value, str):
        return False
    compact = re.sub(r"\s+", "", value)
    if len(compact) < 64 or len(compact) % 4 == 1:
        return False
    if re.fullmatch(r"[A-Za-z0-9+/_-]*={0,2}", compact) is None:
        return False
    try:
        decoded = base64.b64decode(
            compact + "=" * (-len(compact) % 4), altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError):
        return False
    return len(decoded) >= 32


def _is_data_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return (
        value.strip().lower().startswith("data:") and ";base64," in value[:256].lower()
    )


def _is_provider_image_base64(value: Any) -> bool:
    """Identify image bytes in provider objects whose payload key is just data."""
    if not isinstance(value, dict) or not isinstance(value.get("data"), str):
        return False
    object_type = str(value.get("type") or "").strip().lower()
    if object_type not in {"image", "base64"}:
        return False
    media_type = (
        str(value.get("media_type") or value.get("mime_type") or "").strip().lower()
    )
    return media_type.startswith("image/")


def sanitize_binary_payload(value: Any) -> Any:
    """Return a copy with inline binary payloads replaced by bounded markers.

    This function is intentionally limited to binary-shaped fields. Ordinary
    Base64 used for authentication, signatures, protocol envelopes, or text is
    not removed unless it is explicitly stored under a binary field name or is
    identified as an image payload by a provider object.
    """
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        provider_image = _is_provider_image_base64(value)
        for key, item in value.items():
            if (
                _is_binary_key(key, item)
                or _is_data_url(item)
                or (
                    provider_image
                    and str(key).strip().lower() == "data"
                    and isinstance(item, str)
                )
            ):
                result[key] = _BINARY_KEY_MARKER
            else:
                result[key] = sanitize_binary_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_binary_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_binary_payload(item) for item in value]
    return value


def _redact_sensitive_values(
    value: Any,
    *,
    inside_secret_object: bool = False,
    allow_token_metadata: bool = False,
    strip_binary: bool = True,
) -> Any:
    """Mask credentials while retaining public metadata in secret objects."""
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            normalized = _normalize_persistence_key(key)
            if inside_secret_object:
                if (
                    allow_token_metadata
                    and normalized in _TOKEN_PUBLIC_METADATA_KEYS
                    and not isinstance(item, (dict, list, tuple))
                ):
                    result[key] = _redact_sensitive_values(
                        item, strip_binary=strip_binary
                    )
                elif isinstance(item, (dict, list, tuple)):
                    result[key] = _redact_sensitive_values(
                        item,
                        inside_secret_object=True,
                        strip_binary=strip_binary,
                    )
                else:
                    result[key] = None if item is None else SECRET_MASK
            elif _is_persistent_secret_key(key):
                if isinstance(item, (dict, list, tuple)):
                    result[key] = _redact_sensitive_values(
                        item,
                        inside_secret_object=True,
                        allow_token_metadata=normalized == "token",
                        strip_binary=strip_binary,
                    )
                else:
                    result[key] = None if item is None else SECRET_MASK
            else:
                result[key] = _redact_sensitive_values(item, strip_binary=strip_binary)
        return result
    if isinstance(value, (list, tuple)):
        if inside_secret_object:
            return [
                (
                    _redact_sensitive_values(
                        item,
                        inside_secret_object=True,
                        strip_binary=strip_binary,
                    )
                    if isinstance(item, (dict, list, tuple))
                    else None if item is None else SECRET_MASK
                )
                for item in value
            ]
        return [
            _redact_sensitive_values(item, strip_binary=strip_binary) for item in value
        ]
    if isinstance(value, str):
        if inside_secret_object:
            return SECRET_MASK
        if strip_binary and _is_data_url(value):
            return _BINARY_KEY_MARKER
        if value.lstrip()[:1] not in {"{", "["}:
            return _mask_inline_secrets(value)
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return _mask_inline_secrets(value)
        if isinstance(parsed, (dict, list)):
            original_parsed = parsed
            if strip_binary:
                parsed = sanitize_binary_payload(parsed)
            safe_parsed = _redact_sensitive_values(parsed, strip_binary=strip_binary)
            if safe_parsed != original_parsed:
                return json.dumps(safe_parsed, ensure_ascii=False)
        return _mask_inline_secrets(value)
    if inside_secret_object and value is not None:
        return SECRET_MASK
    return value


def sanitize_persistent_value(value: Any) -> Any:
    """Return a copy safe for durable Tool Result storage.

    Binary-shaped payloads and secret-bearing fields are masked recursively.
    Unlike ``mask_args``, this helper does not truncate ordinary strings; the
    persistence boundary applies a separate explicit byte budget.
    """
    return _redact_sensitive_values(sanitize_binary_payload(value))


def redact_persistent_secrets(value: Any) -> Any:
    """Redact secret-bearing values without dropping binary-shaped content."""
    return _redact_sensitive_values(value, strip_binary=False)


def sanitize_persistent_text(text: str) -> str:
    """Redact a textual artifact payload while preserving valid JSON when possible."""
    value = str(text or "")
    if value.lstrip()[:1] not in {"{", "["}:
        return str(sanitize_persistent_value(value))
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        sanitized = sanitize_persistent_value(value)
        return str(sanitized)
    sanitized = sanitize_persistent_value(parsed)
    if sanitized == parsed:
        return value
    return json.dumps(sanitized, ensure_ascii=False, sort_keys=True)


def _take_utf8_prefix(text: str, max_bytes: int) -> str:
    parts: list[str] = []
    used = 0
    for char in text:
        size = len(char.encode("utf-8", errors="replace"))
        if used + size > max_bytes:
            break
        parts.append(char)
        used += size
    return "".join(parts)


def _take_utf8_suffix(text: str, max_bytes: int) -> str:
    parts: list[str] = []
    used = 0
    for char in reversed(text):
        size = len(char.encode("utf-8", errors="replace"))
        if used + size > max_bytes:
            break
        parts.append(char)
        used += size
    return "".join(reversed(parts))


def _truncate_utf8_preview(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    if len(text.encode("utf-8", errors="replace")) <= max_bytes:
        return text
    marker = "\n[persisted result preview truncated]\n"
    marker_bytes = len(marker.encode("utf-8"))
    if marker_bytes >= max_bytes:
        return _take_utf8_prefix(text, max_bytes)
    remaining = max_bytes - marker_bytes
    head_bytes = (remaining + 1) // 2
    tail_bytes = remaining - head_bytes
    return (
        _take_utf8_prefix(text, head_bytes)
        + marker
        + _take_utf8_suffix(text, tail_bytes)
    )


def bounded_persistent_json(
    value: Any,
    max_bytes: int,
    *,
    artifact_ref: str = "",
) -> str:
    """Serialize a safe history projection within a UTF-8 byte budget."""
    if max_bytes < len(b"null"):
        raise ValueError("persistent JSON byte budget is too small")
    omitted = json.dumps({"_uagent_persisted_history": "omitted"})
    if max_bytes < len(omitted.encode("utf-8")):
        return "null"
    safe_value = sanitize_persistent_value(value)
    serialized = json.dumps(safe_value, ensure_ascii=False, sort_keys=True)
    original_bytes = len(serialized.encode("utf-8", errors="replace"))
    if original_bytes <= max_bytes:
        return serialized

    reference = _mask_inline_secrets(str(artifact_ref or ""))
    fixed: dict[str, Any] = {
        "_uagent_persisted_history": "truncated",
        "original_bytes": original_bytes,
    }
    if reference:
        fixed["artifact_ref"] = reference
    minimal = json.dumps(fixed, ensure_ascii=False, sort_keys=True)
    if len(minimal.encode("utf-8", errors="replace")) > max_bytes:
        fixed.pop("artifact_ref", None)
        minimal = json.dumps(fixed, ensure_ascii=False, sort_keys=True)
    if len(minimal.encode("utf-8", errors="replace")) > max_bytes:
        return json.dumps({"_uagent_persisted_history": "omitted"})

    preview_budget = max(0, max_bytes - len(minimal.encode("utf-8")) - 32)
    while True:
        candidate = dict(fixed)
        candidate["preview"] = _truncate_utf8_preview(serialized, preview_budget)
        encoded = json.dumps(candidate, ensure_ascii=False, sort_keys=True)
        if len(encoded.encode("utf-8", errors="replace")) <= max_bytes:
            return encoded
        if preview_budget <= 0:
            return minimal
        preview_budget //= 2


def sanitize_message_for_history(message: Any) -> Any:
    """Sanitize only tool messages, leaving user/assistant messages unchanged."""
    if not isinstance(message, dict) or str(message.get("role") or "") != "tool":
        return message
    return sanitize_persistent_value(message)


__all__ = [
    "bounded_persistent_json",
    "redact_persistent_secrets",
    "sanitize_binary_payload",
    "sanitize_message_for_history",
    "sanitize_persistent_text",
    "sanitize_persistent_value",
]

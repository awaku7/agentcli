"""Privacy filtering for remotely exported observability attributes."""

from __future__ import annotations

from typing import Any, Mapping

_ALWAYS_BLOCKED_FRAGMENTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "client_secret",
    "principal_id",
    "subject",
    "display_name",
    "email",
    "group",
    "room_id",
    "project_id",
    "session_id",
)
_CONTENT_FRAGMENTS = (
    "content",
    "prompt",
    "response_body",
    "reasoning",
    "tool.arguments",
    "tool.result",
    "memory.body",
    "artifact.body",
    "file.body",
)
_MAX_STRING_LENGTH = 512


def _contains_token_credential_key(normalized: str) -> bool:
    """Block credential-style ``token`` keys without hiding token metrics.

    Splitting common key separators means names such as ``access_token``,
    ``auth.token`` and ``bearer-token`` are rejected while plural metric names
    such as ``uag.tokens.reported.input`` and ``gen_ai.usage.input_tokens`` are
    preserved.
    """

    canonical = normalized.replace("_", ".").replace("-", ".").replace("/", ".")
    return "token" in {part for part in canonical.split(".") if part}


def _blocked(key: str, *, capture_content: bool) -> bool:
    normalized = str(key or "").strip().lower()
    if any(fragment in normalized for fragment in _ALWAYS_BLOCKED_FRAGMENTS):
        return True
    if _contains_token_credential_key(normalized):
        return True
    if not capture_content and any(
        fragment in normalized for fragment in _CONTENT_FRAGMENTS
    ):
        return True
    return False


def _sanitize_value(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]
    if isinstance(value, (tuple, list)):
        sanitized = []
        for item in value:
            safe = _sanitize_value(item)
            if safe is not None and isinstance(safe, (bool, int, float, str)):
                sanitized.append(safe)
        return tuple(sanitized)
    return str(value)[:_MAX_STRING_LENGTH]


def sanitize_attributes(
    attributes: Mapping[str, Any] | None,
    *,
    capture_content: bool = False,
) -> dict[str, Any]:
    """Return an OTel-safe metadata-only attribute mapping.

    Identity/session/authorization secrets are always excluded. Content-like
    fields are excluded unless the server/operator explicitly enables content
    capture. Runtime instrumentation should still prefer metadata-only inputs.
    """

    safe: dict[str, Any] = {}
    for key, value in dict(attributes or {}).items():
        name = str(key or "").strip()
        if not name or _blocked(name, capture_content=capture_content):
            continue
        sanitized = _sanitize_value(value)
        if sanitized is not None:
            safe[name] = sanitized
    return safe


__all__ = ["sanitize_attributes"]

"""WebSocket Origin policy for browser-facing UAG Web connections."""

from __future__ import annotations

import ipaddress
import os
import re
from urllib.parse import urlsplit

from ..env_utils import strip_outer_quotes
from .identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
    resolve_identity_mode,
)

_DEFAULT_LOCAL_ORIGINS = frozenset(
    {
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://[::1]:8000",
    }
)


def _contains_ascii_control(value: str) -> bool:
    return any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)


def _raw_allowed_origins_setting() -> str:
    return str(os.environ.get("UAGENT_WEB_ALLOWED_ORIGINS", "") or "")


def _normalize_origin(value: str) -> str:
    raw = str(value or "")
    if _contains_ascii_control(raw):
        raise ValueError("origin contains control characters")
    text = raw.strip()
    if not text or text.casefold() == "null":
        raise ValueError("origin is empty or opaque")
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("origin URL is invalid") from exc
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("origin scheme must be http or https")
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("origin must contain only scheme, host, and optional port")

    scheme = parsed.scheme.casefold()
    host = parsed.hostname.casefold().rstrip(".")
    if not host:
        raise ValueError("origin host is required")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if len(host) > 253:
            raise ValueError("origin host is invalid")
        labels = host.split(".")
        if any(
            not re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
                label,
            )
            for label in labels
        ):
            raise ValueError("origin host is invalid")
    authority = f"[{host}]" if ":" in host else host
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        authority = f"{authority}:{port}"
    return f"{scheme}://{authority}"


def configured_websocket_origins(mode: str | None = None) -> frozenset[str]:
    """Return the exact trusted browser origins for WebSocket handshakes."""

    raw_setting = _raw_allowed_origins_setting()
    if _contains_ascii_control(raw_setting):
        raise IdentityConfigurationError(
            "UAGENT_WEB_ALLOWED_ORIGINS contains an invalid origin"
        )
    raw = strip_outer_quotes(raw_setting)
    if raw:
        origins: set[str] = set()
        for value in raw.split(","):
            if _contains_ascii_control(value):
                raise IdentityConfigurationError(
                    "UAGENT_WEB_ALLOWED_ORIGINS contains an invalid origin"
                )
            candidate = value.strip()
            if not candidate:
                continue
            try:
                origins.add(_normalize_origin(candidate))
            except ValueError as exc:
                raise IdentityConfigurationError(
                    "UAGENT_WEB_ALLOWED_ORIGINS contains an invalid origin"
                ) from exc
        if not origins:
            raise IdentityConfigurationError(
                "UAGENT_WEB_ALLOWED_ORIGINS must contain at least one origin"
            )
        return frozenset(origins)

    selected = resolve_identity_mode(mode)
    if selected == "local":
        return _DEFAULT_LOCAL_ORIGINS
    raise IdentityConfigurationError(
        "UAGENT_WEB_ALLOWED_ORIGINS is required for non-local WebSocket access"
    )


def validate_websocket_origin(
    request_context: object,
    mode: str | None = None,
) -> str:
    """Validate one browser Origin before accepting a WebSocket connection."""

    headers = getattr(request_context, "headers", None)
    try:
        origin = str((headers or {}).get("origin") or "")
    except (AttributeError, TypeError, ValueError) as exc:
        raise IdentityResolutionError("WebSocket Origin is unavailable") from exc
    if not origin:
        raise IdentityResolutionError("WebSocket Origin is required")
    try:
        normalized = _normalize_origin(origin)
    except ValueError as exc:
        raise IdentityResolutionError("WebSocket Origin is invalid") from exc
    if normalized not in configured_websocket_origins(mode):
        raise IdentityResolutionError("WebSocket Origin is not allowed")
    return normalized


__all__ = [
    "configured_websocket_origins",
    "validate_websocket_origin",
]

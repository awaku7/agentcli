"""Anonymous, browser-bound identity cookies for single-browser Web sessions.

This is a per-browser guest identifier, not proof of a real-world user identity.
The signed cookie is a bearer capability and must not be treated as enterprise
authentication.
"""

from __future__ import annotations

import hashlib
import hmac
from http.cookies import SimpleCookie
import os
import re
import secrets
import time
from typing import Any, Callable

from ..env_utils import env_get
from .identity_context import (
    IdentityConfigurationError,
    IdentityContext,
    IdentityResolutionError,
)

BROWSER_SESSION_COOKIE = "uag_browser_session"
_TOKEN_RE = re.compile(r"^(\d{1,12})\.([A-Za-z0-9_-]{32})\.([0-9a-f]{64})$")
_DEFAULT_TTL_SECONDS = 31536000
_MAX_TTL_SECONDS = 10 * 365 * 24 * 60 * 60


def _max_age() -> int:
    from .auth_management import positive_integer_setting

    return min(
        positive_integer_setting("UAGENT_BROWSER_SESSION_TTL", _DEFAULT_TTL_SECONDS),
        _MAX_TTL_SECONDS,
    )


def _signing_key() -> bytes:
    configured = str(env_get("UAGENT_BROWSER_SESSION_SECRET", "") or "")
    if configured:
        key = configured.encode("utf-8")
        if len(key) < 32:
            raise IdentityResolutionError(
                "UAGENT_BROWSER_SESSION_SECRET must contain at least 32 bytes"
            )
        return key

    from ..utils.paths import get_state_dir

    state_dir = get_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    key_path = state_dir / "browser_session.key"
    try:
        descriptor = os.open(
            key_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError:
        try:
            key = key_path.read_bytes()
        except OSError as exc:
            raise IdentityResolutionError("browser session key is unavailable") from exc
    except OSError as exc:
        raise IdentityResolutionError("browser session key cannot be created") from exc
    else:
        key = secrets.token_bytes(32)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(key)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            try:
                key_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise IdentityResolutionError(
                "browser session key cannot be saved"
            ) from exc
    if len(key) != 32:
        raise IdentityResolutionError("browser session key has invalid length")
    if key_path.is_symlink():
        raise IdentityResolutionError("browser session key must not be a symlink")
    if os.name != "nt":
        try:
            if os.stat(key_path).st_mode & 0o077:
                raise IdentityResolutionError(
                    "browser session key permissions must be owner-only"
                )
        except OSError as exc:
            raise IdentityResolutionError("browser session key is unavailable") from exc
    return key


def _token_signature(payload: str) -> str:
    return hmac.new(_signing_key(), payload.encode("ascii"), hashlib.sha256).hexdigest()


def _mint_token(now: int | None = None) -> str:
    issued = int(time.time() if now is None else now)
    payload = f"{issued}.{secrets.token_urlsafe(24)}"
    return f"{payload}.{_token_signature(payload)}"


def valid_browser_session_token(value: object, *, now: int | None = None) -> str:
    token = str(value or "").strip()
    match = _TOKEN_RE.fullmatch(token)
    if match is None:
        return ""
    issued_text, nonce, signature = match.groups()
    payload = f"{issued_text}.{nonce}"
    try:
        issued = int(issued_text)
        current = int(time.time() if now is None else now)
        ttl = _max_age()
        expected = _token_signature(payload)
    except (IdentityResolutionError, ValueError, OSError):
        return ""
    if not hmac.compare_digest(signature, expected):
        return ""
    if issued > current + 60 or current - issued >= ttl:
        return ""
    return token


def browser_identity_from_token(token: str) -> IdentityContext:
    """Derive an opaque stable guest principal from a valid cookie token."""
    token = valid_browser_session_token(token)
    if not token:
        raise IdentityResolutionError("browser session cookie is missing or invalid")
    subject = hashlib.sha256(token.encode("ascii")).hexdigest()
    return IdentityContext(
        principal_id=f"browser:{subject}",
        authenticated=True,
        authn_kind="browser",
        issuer="uag-browser-session",
        subject=subject,
        display_name="Browser guest",
    )


def _secure_cookie(scope: dict[str, Any]) -> bool:
    configured = str(env_get("UAGENT_BROWSER_COOKIE_SECURE", "") or "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False
    return str(scope.get("scheme") or "").lower() in {"https", "wss"}


class BrowserIdentityCookieMiddleware:
    """Mint and refresh a signed guest cookie for HTTP and WebSocket requests."""

    def __init__(self, app: Callable[..., Any]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        from .identity_context import resolve_identity_mode

        try:
            if resolve_identity_mode() != "browser":
                await self.app(scope, receive, send)
                return
        except Exception:
            await self.app(scope, receive, send)
            return

        # Logout must not mint a replacement guest identity when the cookie is
        # missing or expired, or its response would immediately undo deletion.
        if scope.get("type") == "http" and scope.get("path") == "/auth/logout":
            await self.app(scope, receive, send)
            return

        headers = list(scope.get("headers") or [])
        cookie_values = [
            value.decode("latin-1")
            for key, value in headers
            if key.lower() == b"cookie"
        ]
        parsed = SimpleCookie()
        try:
            parsed.load("; ".join(cookie_values))
            presented = (
                parsed.get(BROWSER_SESSION_COOKIE).value
                if parsed.get(BROWSER_SESSION_COOKIE)
                else ""
            )
        except Exception:
            presented = ""
        try:
            cookie_max_age = _max_age()
            token = valid_browser_session_token(presented)
            issued_cookie = not token
            if issued_cookie:
                token = _mint_token()
        except (IdentityConfigurationError, IdentityResolutionError):
            # Let the endpoint report its normal configuration/authentication
            # error instead of crashing in middleware before route handling.
            await self.app(scope, receive, send)
            return

        if issued_cookie:
            cookie_header = "; ".join(cookie_values)
            cookie_header = (
                f"{cookie_header}; {BROWSER_SESSION_COOKIE}={token}"
                if cookie_header
                else f"{BROWSER_SESSION_COOKIE}={token}"
            )
            headers = [
                (key, value) for key, value in headers if key.lower() != b"cookie"
            ]
            headers.append((b"cookie", cookie_header.encode("latin-1")))
            scope = dict(scope)
            scope["headers"] = headers

        async def send_with_cookie(message) -> None:
            if issued_cookie and message.get("type") in {
                "http.response.start",
                "websocket.accept",
            }:
                value = (
                    f"{BROWSER_SESSION_COOKIE}={token}; Max-Age={cookie_max_age}; Path=/; "
                    "HttpOnly; SameSite=Lax"
                )
                if _secure_cookie(scope):
                    value += "; Secure"
                message = dict(message)
                message["headers"] = list(message.get("headers") or []) + [
                    (b"set-cookie", value.encode("latin-1"))
                ]
            await send(message)

        await self.app(scope, receive, send_with_cookie)

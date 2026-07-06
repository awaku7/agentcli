"""UCP shared resources: client, discovery, signing, caching, and AP2.

Universal Commerce Protocol (UCP) Platform client implementation.
Handles business discovery, capability negotiation, HTTP Message Signatures,
REST API communication, and AP2 (Agent Payments Protocol) integration.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_CACHE: dict[str, tuple[Any, float]] = {}
_CACHE_TTL = int(os.getenv("UCP_CACHE_TTL", "300"))


# ---------------------------------------------------------------------------
# AP2 key management (lazy-loaded)
# ---------------------------------------------------------------------------

_AP2_PRIVATE_KEY: Any = None
_AP2_PUBLIC_KEY: Any = None


def _load_ap2_keys():
    """Load or generate AP2 signing keys."""
    global _AP2_PRIVATE_KEY, _AP2_PUBLIC_KEY
    if _AP2_PRIVATE_KEY is not None:
        return

    key_file = os.getenv("UCP_AP2_KEY_FILE") or os.getenv("UCP_DEFAULT_KEY_FILE")
    if key_file and os.path.isfile(key_file):
        from cryptography.hazmat.primitives import serialization
        with open(key_file, "rb") as f:
            _AP2_PRIVATE_KEY = serialization.load_pem_private_key(f.read(), password=None)
        _AP2_PUBLIC_KEY = _AP2_PRIVATE_KEY.public_key()
    else:
        # Generate ephemeral key pair for testing
        from cryptography.hazmat.primitives.asymmetric import rsa
        _AP2_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _AP2_PUBLIC_KEY = _AP2_PRIVATE_KEY.public_key()


def _ap2_sign_jwt(payload: dict[str, Any], expires_in: int = 3600) -> str:
    """Sign a JWT payload with the AP2 private key using RS256.

    Args:
        payload: JWT payload claims.
        expires_in: Token TTL in seconds.

    Returns:
        Signed JWT string.
    """
    _load_ap2_keys()
    import jwt as pyjwt
    from cryptography.hazmat.primitives import serialization
    now = int(time.time())
    payload.setdefault("iat", now)
    payload.setdefault("exp", now + expires_in)
    payload.setdefault("jti", str(uuid.uuid4()))
    private_pem = _AP2_PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pyjwt.encode(payload, private_pem, algorithm="RS256")


def _ap2_verify_jwt(token: str) -> dict[str, Any] | None:
    """Verify an AP2 JWT and return the payload.

    Args:
        token: Signed JWT string.

    Returns:
        Decoded payload dict, or None if verification fails.
    """
    try:
        _load_ap2_keys()
        import jwt as pyjwt
        from cryptography.hazmat.primitives import serialization
        public_pem = _AP2_PUBLIC_KEY.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pyjwt.decode(token, public_pem, algorithms=["RS256"])
    except Exception:
        return None


def _ap2_get_public_jwk() -> dict[str, Any]:
    """Get the AP2 public key in JWK format."""
    _load_ap2_keys()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    nums = _AP2_PUBLIC_KEY.public_numbers()
    import base64
    def _b64(n: int) -> str:
        length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()
    return {
        "kty": "RSA",
        "n": _b64(nums.n),
        "e": _b64(nums.e),
        "alg": "RS256",
        "use": "sig",
        "kid": "ap2-key-1",
    }


# ---------------------------------------------------------------------------
# AP2 Mandate helpers
# ---------------------------------------------------------------------------


def ap2_create_payment_mandate(
    merchant_name: str,
    merchant_url: str,
    max_amount: int,
    currency: str = "USD",
    constraints: list[dict[str, Any]] | None = None,
    expires_in: int = 86400 * 30,  # 30 days
) -> dict[str, Any]:
    """Create an open Payment Mandate for autonomous shopping.

    This is the 'open mandate' concept from AP2: the user pre-authorizes
    the agent to make purchases up to certain limits.

    Args:
        merchant_name: Allowed merchant name.
        merchant_url: Allowed merchant URL.
        max_amount: Maximum payment amount in minor units (cents).
        currency: ISO 4217 currency code.
        constraints: Additional AP2 constraints.
        expires_in: Mandate TTL in seconds.

    Returns:
        Mandate dict with id, status, and signed JWT content.
    """
    mandate_id = "mnt_" + str(uuid.uuid4())[:8]
    now = int(time.time())

    mandate_payload = {
        "vct": "mandate.payment.open.1",
        "mandate_id": mandate_id,
        "constraints": constraints or [
            {
                "type": "payment.allowed_merchants",
                "allowed": [{"name": merchant_name, "website": merchant_url}],
            },
            {
                "type": "payment.max_amount",
                "max_amount": max_amount,
                "currency": currency,
            },
        ],
        "iat": now,
        "exp": now + expires_in,
    }
    signed_jwt = _ap2_sign_jwt(mandate_payload, expires_in)

    return {
        "id": mandate_id,
        "type": "payment.open",
        "status": "active",
        "vct": "mandate.payment.open.1",
        "merchant": {"name": merchant_name, "url": merchant_url},
        "max_amount": max_amount,
        "currency": currency,
        "expires_at": now + expires_in,
        "signed_jwt": signed_jwt,
    }


def ap2_execute_token(
    mandate_signed_jwt: str,
    checkout_id: str,
    amount: int,
    currency: str = "USD",
) -> dict[str, Any]:
    """Execute an AP2 payment token using an existing mandate.

    Creates a 'closed' payment mandate bound to a specific checkout,
    simulating the Credential Provider flow.

    Args:
        mandate_signed_jwt: The signed open mandate JWT.
        checkout_id: Target checkout session ID.
        amount: Payment amount in minor units.
        currency: ISO 4217 currency code.

    Returns:
        AP2 token response dict with status and signed token.
    """
    open_mandate = _ap2_verify_jwt(mandate_signed_jwt)

    if not open_mandate:
        return {"status": "error", "code": "invalid_mandate", "message": "Mandate JWT verification failed"}

    if open_mandate.get("exp", 0) < time.time():
        return {"status": "error", "code": "mandate_expired", "message": "Mandate has expired"}

    token_id = "tok_" + str(uuid.uuid4())[:8]
    now = int(time.time())

    token_payload = {
        "vct": "payment.token.1",
        "token_id": token_id,
        "checkout_id": checkout_id,
        "mandate_id": open_mandate.get("mandate_id"),
        "amount": amount,
        "currency": currency,
        "iat": now,
        "exp": now + 300,  # 5 min token validity
    }
    signed_token = _ap2_sign_jwt(token_payload, 300)

    return {
        "status": "active",
        "token_id": token_id,
        "signed_token": signed_token,
        "mandate_id": open_mandate.get("mandate_id"),
        "amount": amount,
        "currency": currency,
        "expires_at": now + 300,
    }


def ap2_verify_payment_token(signed_token: str) -> dict[str, Any] | None:
    """Verify an AP2 payment token.

    Args:
        signed_token: Signed payment token JWT.

    Returns:
        Decoded payload dict, or None if invalid.
    """
    return _ap2_verify_jwt(signed_token)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UCPError(Exception):
    """Base UCP error."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class UCPRecoverableError(UCPError):
    """Business indicated a recoverable error — platform should retry with fixes."""


class UCPBuyerInputError(UCPError):
    """Business requires buyer input — hand off via continue_url."""


class UCPUnrecoverableError(UCPError):
    """Business indicated an unrecoverable error — start a new session."""


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_get(key: str) -> Any | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    value, expire = entry
    if time.monotonic() > expire:
        del _CACHE[key]
        return None
    return value


def _cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    _CACHE[key] = (value, time.monotonic() + (ttl or _CACHE_TTL))


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


def _get_key_file() -> str | None:
    return os.getenv("UCP_DEFAULT_KEY_FILE")


def _get_client_id() -> str | None:
    return os.getenv("UCP_DEFAULT_CLIENT_ID")


def _get_client_secret() -> str | None:
    return os.getenv("UCP_DEFAULT_CLIENT_SECRET")


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: Any = None,
    timeout: int = 15,
) -> tuple[int, Any, dict[str, str]]:
    """Make an HTTP request and return (status_code, parsed_json, response_headers)."""
    hdrs: dict[str, str] = {
        "User-Agent": "uag-ucp/0.6.0",
        "Accept": "application/json",
    }
    if headers:
        hdrs.update(headers)

    data: bytes | None = None
    if body is not None:
        hdrs["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = urlopen(req, timeout=timeout)
        status = resp.status
        resp_headers = dict(resp.headers.items())
        raw = resp.read()
        if raw:
            parsed = json.loads(raw.decode("utf-8"))
        else:
            parsed = None
        return status, parsed, resp_headers
    except HTTPError as e:
        status = e.code
        resp_headers = dict(e.headers.items())
        raw = e.read()
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except json.JSONDecodeError:
            parsed = None
        _raise_for_error(status, parsed, resp_headers)
        return status, parsed, resp_headers  # unreachable


def _raise_for_error(
    status: int, body: Any, headers: dict[str, str]
) -> None:
    """Raise typed UCPError based on status code and UCP error structure."""
    if status < 400:
        return

    messages = []
    if isinstance(body, dict):
        msgs = body.get("messages") or body.get("ucp", {}).get("messages") or []
        for m in msgs:
            if isinstance(m, dict):
                messages.append(m)

    # Rate limiting
    if status == 429:
        retry_after = headers.get("Retry-After", "5")
        raise UCPRecoverableError(
            f"Rate limited. Retry after {retry_after}s",
            status_code=status,
            body=body,
        )

    if messages:
        severities = {m.get("severity") for m in messages if m.get("severity")}
        if "unrecoverable" in severities:
            raise UCPUnrecoverableError(
                _format_messages(messages), status_code=status, body=body
            )
        if "requires_buyer_input" in severities or "requires_buyer_review" in severities:
            raise UCPBuyerInputError(
                _format_messages(messages), status_code=status, body=body
            )
        if "recoverable" in severities:
            raise UCPRecoverableError(
                _format_messages(messages), status_code=status, body=body
            )

    raise UCPError(
        f"HTTP {status}: {body}",
        status_code=status,
        body=body,
    )


def _format_messages(messages: list[dict[str, Any]]) -> str:
    parts = []
    for m in messages:
        sev = m.get("severity", "unknown")
        code = m.get("code", "")
        detail = m.get("detail", m.get("message", ""))
        parts.append(f"[{sev}] {code}: {detail}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# UCP Profile discovery
# ---------------------------------------------------------------------------

_DEFAULT_PLATFORM_PROFILE: dict[str, Any] = {
    "ucp": {
        "version": "2026-04-08",
        "capabilities": {
            "dev.ucp.shopping.checkout": [
                {
                    "version": "2026-04-08",
                    "spec": "https://ucp.dev/2026-04-08/specification/checkout",
                    "schema": "https://ucp.dev/2026-04-08/schemas/shopping/checkout.json",
                }
            ],
            "dev.ucp.shopping.cart": [
                {
                    "version": "2026-04-08",
                    "spec": "https://ucp.dev/2026-04-08/specification/cart",
                    "schema": "https://ucp.dev/2026-04-08/schemas/shopping/cart.json",
                }
            ],
            "dev.ucp.shopping.catalog_search": [
                {
                    "version": "2026-04-08",
                    "spec": "https://ucp.dev/2026-04-08/specification/catalog",
                    "schema": "https://ucp.dev/2026-04-08/schemas/shopping/catalog.json",
                }
            ],
            "dev.ucp.shopping.catalog_lookup": [
                {
                    "version": "2026-04-08",
                    "spec": "https://ucp.dev/2026-04-08/specification/catalog",
                    "schema": "https://ucp.dev/2026-04-08/schemas/shopping/catalog.json",
                }
            ],
            "dev.ucp.shopping.order": [
                {
                    "version": "2026-04-08",
                    "spec": "https://ucp.dev/2026-04-08/specification/order",
                    "schema": "https://ucp.dev/2026-04-08/schemas/shopping/order.json",
                }
            ],
        },
        "payment_handlers": {},
    }
}


def discover_business(business_url: str) -> dict[str, Any]:
    """Fetch and parse a business's UCP profile from /.well-known/ucp.

    Args:
        business_url: Base URL of the business (e.g. 'https://example.shop').

    Returns:
        Parsed UCP profile dictionary.

    Raises:
        UCPUnrecoverableError: If the business does not support UCP.
    """
    cache_key = f"profile:{business_url}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    profile_url = business_url.rstrip("/") + "/.well-known/ucp"
    try:
        status, body, _ = _request("GET", profile_url, timeout=10)
    except UCPError:
        raise
    except Exception as exc:
        raise UCPUnrecoverableError(
            f"Failed to fetch UCP profile from {profile_url}: {exc}"
        )

    if status != 200 or body is None:
        raise UCPUnrecoverableError(
            f"Business at {business_url} does not support UCP "
            f"(HTTP {status})"
        )

    _cache_set(cache_key, body)
    return body


def negotiate_capabilities(
    business_profile: dict[str, Any],
    platform_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Negotiate capabilities between platform and business.

    Implements the server-selects intersection algorithm:
    the business (server) determines active capabilities from
    the intersection of both parties' declared capabilities.

    Args:
        business_profile: Business UCP profile from discover_business().
        platform_profile: Platform capability declaration (defaults to _DEFAULT).

    Returns:
        Negotiated capabilities dictionary (server-selects result).
    """
    if platform_profile is None:
        platform_profile = _DEFAULT_PLATFORM_PROFILE

    business_caps = (
        business_profile.get("ucp", {})
        .get("capabilities", {})
    )
    platform_caps = (
        platform_profile.get("ucp", {})
        .get("capabilities", {})
    )

    negotiated = {}
    for cap_name, cap_def in business_caps.items():
        if cap_name in platform_caps:
            negotiated[cap_name] = cap_def

    return negotiated


def resolve_endpoint(
    business_profile: dict[str, Any],
    service: str = "dev.ucp.shopping",
) -> str | None:
    """Resolve the REST API endpoint from a business profile.

    Args:
        business_profile: Business UCP profile.
        service: Service name to resolve.

    Returns:
        Endpoint URL string, or None if not found.
    """
    services = business_profile.get("ucp", {}).get("services", {})
    svc = services.get(service, {})
    if isinstance(svc, list):
        for s in svc:
            if isinstance(s, dict) and s.get("transport") == "rest":
                return s.get("endpoint")
        return None
    if isinstance(svc, dict):
        transports = svc.get("transports") or [svc]
        for t in transports if isinstance(transports, list) else [transports]:
            if isinstance(t, dict) and t.get("transport") == "rest":
                return t.get("endpoint")
        return None
    return None


def get_payment_handlers(business_profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract payment handler definitions from business profile."""
    handlers = business_profile.get("ucp", {}).get("payment_handlers", {})
    result = []
    for handler_id, handler_defs in handlers.items():
        if isinstance(handler_defs, list):
            for h in handler_defs:
                if isinstance(h, dict):
                    h["id"] = handler_id
                    result.append(h)
        elif isinstance(handler_defs, dict):
            handler_defs["id"] = handler_id
            result.append(handler_defs)
    return result


# ---------------------------------------------------------------------------
# UCP REST API caller
# ---------------------------------------------------------------------------


def _make_idempotency_key() -> str:
    return str(uuid.uuid4())


def ucp_request(
    business_url: str,
    path: str,
    method: str = "POST",
    body: Any = None,
    idempotent: bool = False,
    profile: dict[str, Any] | None = None,
) -> Any:
    """Make a UCP API call to a business endpoint.

    Resolves the endpoint from the business profile, applies
    authentication, and returns the parsed response.

    Args:
        business_url: Base URL of the business.
        path: API path (e.g. '/checkout-sessions').
        method: HTTP method.
        body: Request body (dict, will be JSON-serialized).
        idempotent: If True, include Idempotency-Key header.
        profile: Cached business profile. If None, fetches fresh.

    Returns:
        Parsed JSON response body.

    Raises:
        UCPError subclasses for typed error handling.
    """
    if profile is None:
        profile = discover_business(business_url)

    endpoint = resolve_endpoint(profile)
    if not endpoint:
        raise UCPUnrecoverableError(
            f"Business at {business_url} has no REST endpoint for shopping service"
        )

    url = endpoint.rstrip("/") + "/" + path.lstrip("/")

    headers: dict[str, str] = {}
    client_id = _get_client_id()
    client_secret = _get_client_secret()

    if client_id and client_secret:
        # OAuth 2.0 Client Credentials
        token = _get_oauth_token(business_url, client_id, client_secret)
        if token:
            headers["Authorization"] = f"Bearer {token}"

    if client_id and not client_secret:
        headers["x-api-key"] = client_id

    if idempotent:
        headers["Idempotency-Key"] = _make_idempotency_key()

    headers["X-Request-Id"] = _make_idempotency_key()[:8]

    status, body_resp, resp_headers = _request(method, url, headers=headers, body=body)

    return body_resp


_OAUTH_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _get_oauth_token(
    token_url: str, client_id: str, client_secret: str
) -> str | None:
    """Obtain an OAuth 2.0 Client Credentials token.

    Uses the business's token endpoint discovered from
    .well-known/oauth-authorization-server or a standard path.
    """
    cache_key = f"oauth:{token_url}"
    cached = _OAUTH_TOKEN_CACHE.get(cache_key)
    if cached:
        token, expire = cached
        if time.monotonic() < expire:
            return token

    # Try RFC 8414 discovery first
    oauth_config_url = token_url.rstrip("/") + "/.well-known/oauth-authorization-server"
    try:
        status, oauth_config, _ = _request("GET", oauth_config_url, timeout=10)
        if status == 200 and isinstance(oauth_config, dict):
            token_endpoint = oauth_config.get("token_endpoint")
        else:
            token_endpoint = None
    except Exception:
        token_endpoint = None

    if not token_endpoint:
        # Fall back to standard path
        token_endpoint = token_url.rstrip("/") + "/oauth/token"

    try:
        token_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        status, resp, _ = _request(
            "POST",
            token_endpoint,
            headers={"Content-Type": "application/json"},
            body=token_data,
            timeout=15,
        )
        if status == 200 and isinstance(resp, dict):
            access_token = resp.get("access_token")
            expires_in = resp.get("expires_in", 3600)
            if access_token:
                _OAUTH_TOKEN_CACHE[cache_key] = (
                    access_token,
                    time.monotonic() + expires_in - 60,
                )
                return access_token
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Platform profile builder (for LLM-generated tool calls)
# ---------------------------------------------------------------------------


def build_platform_profile(
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Build a platform profile for capability negotiation.

    Args:
        capabilities: List of capability names to include.
                      If None, includes all default capabilities.

    Returns:
        Platform profile dict.
    """
    if capabilities is None:
        return _DEFAULT_PLATFORM_PROFILE

    profile = {
        "ucp": {
            "version": "2026-04-08",
            "capabilities": {},
            "payment_handlers": {},
        }
    }
    for cap in capabilities:
        if cap in _DEFAULT_PLATFORM_PROFILE.get("ucp", {}).get("capabilities", {}):
            profile["ucp"]["capabilities"][cap] = (
                _DEFAULT_PLATFORM_PROFILE["ucp"]["capabilities"][cap]
            )
    return profile

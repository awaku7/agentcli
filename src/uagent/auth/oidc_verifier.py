"""OIDC discovery and signed ID-token validation.

These primitives do not authenticate an HTTP request on their own. A caller
must supply the nonce from a previously consumed browser-bound transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from urllib.parse import urlsplit

import httpx
import jwt

from ..runtime.identity_context import IdentityContext, IdentityResolutionError

_MAX_DOCUMENT_BYTES = 1_000_000
_ALLOWED_ALGORITHMS = ("RS256",)


@dataclass(frozen=True)
class OIDCProviderMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


def _https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _get_json(url: str) -> dict:
    with httpx.Client(timeout=5.0, follow_redirects=False) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > _MAX_DOCUMENT_BYTES:
                    raise IdentityResolutionError("OIDC document exceeds size limit")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise IdentityResolutionError("invalid OIDC document")
    return data


def discover_provider(issuer: str) -> OIDCProviderMetadata:
    """Read HTTPS discovery and require the configured issuer exactly."""
    if not _https_url(issuer):
        raise IdentityResolutionError("invalid OIDC issuer URL")
    try:
        discovery_base = issuer.rstrip("/")
        document = _get_json(discovery_base + "/.well-known/openid-configuration")
        if document.get("issuer") != issuer:
            raise IdentityResolutionError("OIDC discovery issuer mismatch")
        endpoints = [
            document.get("authorization_endpoint"),
            document.get("token_endpoint"),
            document.get("jwks_uri"),
        ]
        if not all(isinstance(value, str) and _https_url(value) for value in endpoints):
            raise IdentityResolutionError("invalid OIDC discovery endpoints")
        return OIDCProviderMetadata(issuer, *endpoints)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise IdentityResolutionError("OIDC discovery failed") from exc


def fetch_jwks(metadata: OIDCProviderMetadata) -> dict:
    """Fetch signing keys from the validated discovery document."""
    try:
        jwks = _get_json(metadata.jwks_uri)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise IdentityResolutionError("OIDC signing keys unavailable") from exc
    if not isinstance(jwks.get("keys"), list):
        raise IdentityResolutionError("invalid OIDC signing keys")
    return jwks


def verify_id_token(
    token: str,
    *,
    metadata: OIDCProviderMetadata,
    jwks: dict,
    client_id: str,
    nonce: str,
) -> IdentityContext:
    """Verify signature and claims before deriving an opaque principal."""
    if not token or len(token) > 16_384 or not client_id or not nonce:
        raise IdentityResolutionError("incomplete OIDC token verification input")
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") not in _ALLOWED_ALGORITHMS or not isinstance(kid, str):
            raise IdentityResolutionError("unsupported OIDC signing algorithm or key")
        matches = [
            key
            for key in jwks.get("keys", [])
            if isinstance(key, dict)
            and key.get("kid") == kid
            and key.get("kty") == "RSA"
            and key.get("use", "sig") == "sig"
        ]
        if len(matches) != 1:
            raise IdentityResolutionError("OIDC signing key not unique")
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matches[0]))
        claims = jwt.decode(
            token,
            public_key,
            algorithms=list(_ALLOWED_ALGORITHMS),
            audience=client_id,
            issuer=metadata.issuer,
            options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]},
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject:
            raise IdentityResolutionError("invalid OIDC subject")
        audience = claims["aud"]
        if isinstance(audience, list) and len(audience) > 1:
            if claims.get("azp") != client_id:
                raise IdentityResolutionError("OIDC authorized party mismatch")
        if "azp" in claims and claims["azp"] != client_id:
            raise IdentityResolutionError("OIDC authorized party mismatch")
        if not isinstance(claims["nonce"], str) or not hmac.compare_digest(
            claims["nonce"], nonce
        ):
            raise IdentityResolutionError("OIDC nonce mismatch")
        principal_hash = hashlib.sha256(
            (metadata.issuer + "\0" + subject).encode("utf-8")
        ).hexdigest()
        return IdentityContext(
            principal_id="oidc:" + principal_hash,
            authenticated=True,
            authn_kind="oidc",
            issuer=metadata.issuer,
            subject=subject,
            display_name=str(claims.get("name") or ""),
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise IdentityResolutionError("OIDC ID token verification failed") from exc

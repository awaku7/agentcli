"""OIDC discovery and signed ID-token validation.

These primitives do not authenticate an HTTP request on their own. A caller
must supply the nonce from a previously consumed browser-bound transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any
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


def _has_group_overage(claims: dict) -> bool:
    claim_names = claims.get("_claim_names")
    return (isinstance(claim_names, dict) and "groups" in claim_names) or (
        claims.get("hasgroups") is True and "groups" not in claims
    )


def _verified_group_claims(claims: dict) -> tuple[str, ...]:
    """Extract signed directory group IDs without accepting overage markers."""
    if _has_group_overage(claims):
        raise IdentityResolutionError(
            "OIDC group overage requires a configured directory API adapter"
        )
    raw_groups = claims.get("groups", [])
    if raw_groups is None:
        raw_groups = []
    if not isinstance(raw_groups, list):
        raise IdentityResolutionError("invalid OIDC group claims")
    groups: list[str] = []
    for group in raw_groups:
        if not isinstance(group, str) or not group.strip():
            raise IdentityResolutionError("invalid OIDC group claims")
        groups.append(group.strip())
    return tuple(groups)


def _verify_id_token(
    token: str,
    metadata: OIDCProviderMetadata,
    jwks: dict,
    client_id: str,
    nonce: str,
) -> tuple[IdentityContext, bool]:
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
        group_overage = _has_group_overage(claims)
        groups = () if group_overage else _verified_group_claims(claims)
        principal_hash = hashlib.sha256(
            (metadata.issuer + "\0" + subject).encode("utf-8")
        ).hexdigest()
        identity = IdentityContext(
            principal_id="oidc:" + principal_hash,
            authenticated=True,
            authn_kind="oidc",
            issuer=metadata.issuer,
            subject=subject,
            display_name=str(claims.get("name") or ""),
            groups=groups,
        )
        return identity, group_overage
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise IdentityResolutionError("OIDC ID token verification failed") from exc


def verify_id_token(
    token: str,
    *,
    metadata: OIDCProviderMetadata,
    jwks: dict,
    client_id: str,
    nonce: str,
) -> IdentityContext:
    """Verify signature and claims, failing closed on unresolved group overage."""
    identity, group_overage = _verify_id_token(token, metadata, jwks, client_id, nonce)
    if group_overage:
        raise IdentityResolutionError(
            "OIDC group overage requires a configured directory API adapter"
        )
    return identity


def verify_id_token_with_overage(
    token: str,
    *,
    metadata: OIDCProviderMetadata,
    jwks: dict,
    client_id: str,
    nonce: str,
) -> tuple[IdentityContext, bool]:
    """Verify the token and separately report its signed overage marker."""
    return _verify_id_token(token, metadata, jwks, client_id, nonce)


_ENTRA_GRAPH_HOSTS = {
    "login.microsoftonline.com": "graph.microsoft.com",
    "login.microsoftonline.us": "graph.microsoft.us",
    "login.chinacloudapi.cn": "microsoftgraph.chinacloudapi.cn",
}
_GRAPH_GROUPS_PATH = "/v1.0/me/transitiveMemberOf/microsoft.graph.group"
_GRAPH_MAX_PAGES = 32
_GRAPH_MAX_GROUPS = 10_000
_GRAPH_MAX_RESPONSE_BYTES = 1_000_000


def _is_trusted_graph_url(value: str, host: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == host
        and port in {None, 443}
        and parsed.username is None
        and parsed.password is None
        and parsed.path == _GRAPH_GROUPS_PATH
        and not parsed.fragment
    )


async def resolve_entra_group_overage(
    identity: IdentityContext,
    access_token: str,
    *,
    http_client: Any,
    configured_scopes: str,
) -> tuple[str, ...]:
    """Resolve signed Entra group overage from Graph without persisting tokens.

    The access token must come from the same authorization-code exchange as the
    verified ID token. Pagination URLs are restricted to the Graph host matching
    that verified Entra issuer before the bearer token is sent.
    """
    issuer = urlsplit(identity.issuer)
    graph_host = _ENTRA_GRAPH_HOSTS.get((issuer.hostname or "").lower())
    if identity.authn_kind != "oidc" or issuer.scheme != "https" or graph_host is None:
        raise IdentityResolutionError(
            "group overage is supported only for configured Microsoft Entra issuers"
        )
    scopes = {part.strip().lower() for part in str(configured_scopes or "").split()}
    if not any(
        scope == "groupmember.read.all" or scope.endswith("/groupmember.read.all")
        for scope in scopes
    ):
        raise IdentityResolutionError(
            "Entra group overage requires UAGENT_OIDC_GRAPH_SCOPE with GroupMember.Read.All consent"
        )
    if (
        not access_token
        or len(access_token) > 65_536
        or any(ord(char) < 33 for char in access_token)
    ):
        raise IdentityResolutionError(
            "Entra group overage requires a valid Graph access token from the OIDC exchange"
        )

    url = f"https://{graph_host}{_GRAPH_GROUPS_PATH}?$select=id&$top=999"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    groups: set[str] = set()
    for _ in range(_GRAPH_MAX_PAGES):
        if not _is_trusted_graph_url(url, graph_host):
            raise IdentityResolutionError(
                "Entra Graph returned an unsafe pagination URL"
            )
        try:
            async with http_client.stream(
                "GET",
                url,
                headers=headers,
                follow_redirects=False,
                timeout=10.0,
            ) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(content) + len(chunk) > _GRAPH_MAX_RESPONSE_BYTES:
                        raise IdentityResolutionError(
                            "Entra Graph response exceeds size limit"
                        )
                    content.extend(chunk)
        except IdentityResolutionError:
            raise
        except Exception as exc:
            raise IdentityResolutionError("Entra group lookup failed") from exc
        try:
            document = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise IdentityResolutionError("Entra Graph returned invalid JSON") from exc
        if not isinstance(document, dict) or not isinstance(
            document.get("value"), list
        ):
            raise IdentityResolutionError("Entra Graph returned an invalid group list")
        for item in document["value"]:
            if not isinstance(item, dict):
                raise IdentityResolutionError("Entra Graph returned an invalid group")
            group_id = item.get("id")
            if (
                not isinstance(group_id, str)
                or not group_id.strip()
                or len(group_id) > 256
                or any(ord(char) < 32 for char in group_id)
            ):
                raise IdentityResolutionError(
                    "Entra Graph returned an invalid group ID"
                )
            groups.add(group_id.strip())
            if len(groups) > _GRAPH_MAX_GROUPS:
                raise IdentityResolutionError("Entra group list exceeds size limit")
        next_url = document.get("@odata.nextLink")
        if not next_url:
            return tuple(sorted(groups))
        if not isinstance(next_url, str) or not _is_trusted_graph_url(
            next_url, graph_host
        ):
            raise IdentityResolutionError(
                "Entra Graph returned an unsafe pagination URL"
            )
        url = next_url
    raise IdentityResolutionError("Entra group pagination exceeds page limit")

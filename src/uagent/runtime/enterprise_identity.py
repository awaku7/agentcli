"""Enterprise identity adapters kept separate from Memory authorization."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import ipaddress
import json
import threading
from typing import Any, Mapping, Protocol

from ..env_utils import env_get
from .identity_context import (
    IdentityConfigurationError,
    IdentityContext,
    IdentityResolutionError,
    IdentityResolver,
)


def opaque_principal_id(kind: str, namespace: str, subject: str) -> str:
    """Derive a stable ownership key without exposing account identifiers."""
    kind = str(kind or "").strip().lower()
    namespace = str(namespace or "").strip()
    subject = str(subject or "").strip()
    if not kind or not namespace or not subject:
        raise IdentityResolutionError("identity namespace and subject are required")
    digest = hashlib.sha256((namespace + "\0" + subject).encode("utf-8")).hexdigest()
    return f"{kind}:{digest}"


@dataclass(frozen=True)
class VerifiedEnterpriseIdentity:
    """Output accepted only from a configured credential validation adapter."""

    namespace: str
    subject: str
    display_name: str = ""
    groups: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.namespace or "").strip() or not str(self.subject or "").strip():
            raise IdentityResolutionError("verified identity is incomplete")
        object.__setattr__(self, "namespace", str(self.namespace).strip())
        object.__setattr__(self, "subject", str(self.subject).strip())
        object.__setattr__(self, "display_name", str(self.display_name or "").strip())
        object.__setattr__(
            self,
            "groups",
            tuple(
                sorted(
                    {str(group).strip() for group in self.groups if str(group).strip()}
                )
            ),
        )


class CredentialVerifier(Protocol):
    def __call__(self, request_context: Any) -> VerifiedEnterpriseIdentity: ...


@dataclass(frozen=True)
class GroupPolicyAssignments:
    """Authorization-only output; groups never become a principal ownership key."""

    administrator: bool = False
    room_roles: tuple[tuple[str, str], ...] = ()
    project_ids: tuple[str, ...] = ()


class DirectoryGroupPolicyAdapter(Protocol):
    def map_groups(
        self, identity: IdentityContext, groups: tuple[str, ...]
    ) -> GroupPolicyAssignments: ...


def _headers(request_context: Any) -> dict[str, str]:
    source = getattr(request_context, "headers", None) or {}
    try:
        return {str(key).casefold(): str(value) for key, value in source.items()}
    except (AttributeError, TypeError, ValueError) as exc:
        raise IdentityResolutionError("request headers are unavailable") from exc


def _bearer_token(request_context: Any) -> str:
    authorization = _headers(request_context).get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not token.strip():
        raise IdentityResolutionError("Bearer credential is missing")
    return token.strip()


class _VerifiedAdapterResolver(IdentityResolver):
    mode = ""

    def __init__(self, verifier: CredentialVerifier):
        if not callable(verifier):
            raise IdentityConfigurationError(f"{self.mode} verifier is not configured")
        self._verifier = verifier

    def resolve(self, request_context: Any = None) -> IdentityContext:
        try:
            verified = self._verifier(request_context)
        except IdentityResolutionError:
            raise
        except Exception as exc:
            raise IdentityResolutionError(
                f"{self.mode} identity verification failed"
            ) from exc
        if not isinstance(verified, VerifiedEnterpriseIdentity):
            raise IdentityResolutionError(
                "identity verifier returned an invalid result"
            )
        return IdentityContext(
            principal_id=opaque_principal_id(
                self.mode, verified.namespace, verified.subject
            ),
            authenticated=True,
            authn_kind=self.mode,
            issuer=verified.namespace,
            subject=verified.subject,
            display_name=verified.display_name,
        )


class OAuthIdentityResolver(_VerifiedAdapterResolver):
    """Resolve a validated OAuth provider user, never token text itself."""

    mode = "oauth"


class WindowsADIdentityResolver(_VerifiedAdapterResolver):
    """Bridge a platform Kerberos/Negotiate validator into IdentityContext."""

    mode = "windows_ad"


class ExternalIdentityResolver(_VerifiedAdapterResolver):
    """Bridge a host-supplied verified identity into the common contract."""

    mode = "external"


class TrustedProxyIdentityResolver(IdentityResolver):
    """Accept identity headers only from an explicitly allowed proxy address."""

    mode = "trusted_proxy"

    def __init__(self) -> None:
        self.identity_header = (
            str(env_get("UAGENT_TRUSTED_PROXY_IDENTITY_HEADER", "") or "")
            .strip()
            .casefold()
        )
        self.issuer_header = (
            str(env_get("UAGENT_TRUSTED_PROXY_ISSUER_HEADER", "") or "")
            .strip()
            .casefold()
        )
        raw_cidrs = str(env_get("UAGENT_TRUSTED_PROXY_CIDRS", "") or "")
        if not self.identity_header or not self.issuer_header or not raw_cidrs.strip():
            raise IdentityConfigurationError(
                "trusted proxy headers and CIDR boundary are required"
            )
        try:
            self.networks = tuple(
                ipaddress.ip_network(value.strip(), strict=False)
                for value in raw_cidrs.split(",")
                if value.strip()
            )
        except ValueError as exc:
            raise IdentityConfigurationError("invalid trusted proxy CIDR") from exc
        if not self.networks:
            raise IdentityConfigurationError("trusted proxy CIDR boundary is required")
        if any(network.prefixlen == 0 for network in self.networks):
            raise IdentityConfigurationError(
                "trusted proxy CIDR must not trust the entire address space"
            )

    def resolve(self, request_context: Any = None) -> IdentityContext:
        client = getattr(request_context, "client", None)
        host = str(getattr(client, "host", "") or "").strip()
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise IdentityResolutionError(
                "trusted proxy source is unavailable"
            ) from exc
        if not any(address in network for network in self.networks):
            raise IdentityResolutionError(
                "request did not arrive through a trusted proxy"
            )
        headers = _headers(request_context)
        subject = headers.get(self.identity_header, "").strip()
        issuer = headers.get(self.issuer_header, "").strip()
        if not subject or not issuer:
            raise IdentityResolutionError("trusted proxy identity headers are missing")
        return IdentityContext(
            principal_id=opaque_principal_id(self.mode, issuer, subject),
            authenticated=True,
            authn_kind=self.mode,
            issuer=issuer,
            subject=subject,
        )


class TokenIdentityResolver(IdentityResolver):
    """Validate a Bearer token against configured hashes and map to a subject."""

    mode = "token"

    def __init__(self) -> None:
        raw = str(env_get("UAGENT_TOKEN_IDENTITIES", "") or "").strip()
        namespace = str(env_get("UAGENT_TOKEN_NAMESPACE", "uag-token") or "").strip()
        if not raw or not namespace:
            raise IdentityConfigurationError("token identities are not configured")
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IdentityConfigurationError(
                "invalid token identity configuration"
            ) from exc
        if not isinstance(entries, list) or not entries:
            raise IdentityConfigurationError(
                "token identities must be a non-empty list"
            )
        parsed: list[tuple[str, str, str]] = []
        seen_digests: set[str] = set()
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise IdentityConfigurationError("invalid token identity entry")
            digest = str(entry.get("token_sha256") or "").strip().lower()
            subject = str(entry.get("subject") or "").strip()
            display_name = str(entry.get("display_name") or "").strip()
            if len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest
            ):
                raise IdentityConfigurationError(
                    "token_sha256 must be a SHA-256 hex digest"
                )
            if not subject:
                raise IdentityConfigurationError("token identity subject is required")
            if digest in seen_digests:
                raise IdentityConfigurationError("duplicate token identity digest")
            seen_digests.add(digest)
            parsed.append((digest, subject, display_name))
        self.namespace = namespace
        self.entries = tuple(parsed)

    def resolve(self, request_context: Any = None) -> IdentityContext:
        credential = _bearer_token(request_context)
        digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()
        match = None
        for expected, subject, display_name in self.entries:
            if hmac.compare_digest(digest, expected):
                match = (subject, display_name)
        if match is None:
            raise IdentityResolutionError("Bearer credential is invalid")
        subject, display_name = match
        return IdentityContext(
            principal_id=opaque_principal_id(self.mode, self.namespace, subject),
            authenticated=True,
            authn_kind=self.mode,
            issuer=self.namespace,
            subject=subject,
            display_name=display_name,
        )


_ADAPTER_VERIFIERS: dict[str, CredentialVerifier] = {}
_ADAPTER_LOCK = threading.Lock()
_ADAPTER_GENERATION = 0


def register_enterprise_identity_verifier(
    mode: str, verifier: CredentialVerifier | None
) -> None:
    """Register a host adapter during trusted server startup, never per request."""
    selected = str(mode or "").strip().lower()
    if selected not in {"oauth", "windows_ad", "external"}:
        raise ValueError("mode does not use an enterprise verifier")
    global _ADAPTER_GENERATION
    with _ADAPTER_LOCK:
        if verifier is None:
            _ADAPTER_VERIFIERS.pop(selected, None)
        elif callable(verifier):
            _ADAPTER_VERIFIERS[selected] = verifier
        else:
            raise TypeError("verifier must be callable")
        _ADAPTER_GENERATION += 1


def enterprise_identity_adapter_state(mode: str) -> tuple[bool, int]:
    """Return non-secret adapter state for validation and session binding."""
    selected = str(mode or "").strip().lower()
    with _ADAPTER_LOCK:
        return selected in _ADAPTER_VERIFIERS, _ADAPTER_GENERATION


def enterprise_resolver(mode: str) -> IdentityResolver:
    if mode == "trusted_proxy":
        return TrustedProxyIdentityResolver()
    if mode == "token":
        return TokenIdentityResolver()
    resolver_types = {
        "oauth": OAuthIdentityResolver,
        "windows_ad": WindowsADIdentityResolver,
        "external": ExternalIdentityResolver,
    }
    resolver_type = resolver_types.get(mode)
    if resolver_type is None:
        raise IdentityConfigurationError(
            f"unsupported enterprise identity mode: {mode}"
        )
    verifier = _ADAPTER_VERIFIERS.get(mode)
    if verifier is None:
        raise IdentityConfigurationError(f"{mode} verifier is not configured")
    return resolver_type(verifier)


__all__ = [
    "CredentialVerifier",
    "DirectoryGroupPolicyAdapter",
    "ExternalIdentityResolver",
    "GroupPolicyAssignments",
    "OAuthIdentityResolver",
    "TokenIdentityResolver",
    "TrustedProxyIdentityResolver",
    "VerifiedEnterpriseIdentity",
    "WindowsADIdentityResolver",
    "enterprise_resolver",
    "enterprise_identity_adapter_state",
    "opaque_principal_id",
    "register_enterprise_identity_verifier",
]

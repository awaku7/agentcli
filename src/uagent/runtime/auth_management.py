"""Safe authentication configuration validation and revision binding."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from urllib.parse import urlparse

from ..env_utils import env_get
from .enterprise_identity import (
    TokenIdentityResolver,
    TrustedProxyIdentityResolver,
    enterprise_identity_adapter_state,
)
from .identity_context import IdentityConfigurationError, resolve_identity_mode


@dataclass(frozen=True)
class AuthenticationStatus:
    mode: str
    configured: bool
    health: str
    provider: str
    diagnostics: tuple[str, ...]

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


_MODE_SETTINGS = {
    "local": (),
    "oidc": (
        "UAGENT_OIDC_ISSUER",
        "UAGENT_OIDC_CLIENT_ID",
        "UAGENT_OIDC_CLIENT_SECRET",
        "UAGENT_OIDC_REDIRECT_URI",
        "UAGENT_OIDC_COOKIE_SECURE",
        "UAGENT_OIDC_SESSION_TTL",
    ),
    "oauth": ("UAGENT_OAUTH_PROVIDER", "UAGENT_OAUTH_CLIENT_ID"),
    "trusted_proxy": (
        "UAGENT_TRUSTED_PROXY_IDENTITY_HEADER",
        "UAGENT_TRUSTED_PROXY_ISSUER_HEADER",
        "UAGENT_TRUSTED_PROXY_CIDRS",
    ),
    "windows_ad": ("UAGENT_WINDOWS_AD_REALM",),
    "token": ("UAGENT_TOKEN_NAMESPACE", "UAGENT_TOKEN_IDENTITIES"),
    "external": ("UAGENT_EXTERNAL_PROVIDER",),
}


def _value(name: str) -> str:
    return str(env_get(name, "") or "").strip()


def authentication_configuration_fingerprint(mode: str | None = None) -> str:
    """Hash security-sensitive configuration without exposing its values."""
    selected = resolve_identity_mode(mode)
    registered, generation = enterprise_identity_adapter_state(selected)
    payload = {
        "mode": selected,
        "settings": {name: _value(name) for name in _MODE_SETTINGS[selected]},
        "adapter_registered": registered,
        "adapter_generation": (
            generation if selected in {"oauth", "windows_ad", "external"} else 0
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_authentication_configuration(
    mode: str | None = None,
) -> AuthenticationStatus:
    """Return actionable setting names and health, never configured values."""
    try:
        selected = resolve_identity_mode(mode)
    except IdentityConfigurationError as exc:
        return AuthenticationStatus("invalid", False, "unconfigured", "", (str(exc),))

    diagnostics: list[str] = []
    provider = ""
    if selected == "local":
        provider = "local"
    elif selected == "oidc":
        required = (
            "UAGENT_OIDC_ISSUER",
            "UAGENT_OIDC_CLIENT_ID",
            "UAGENT_OIDC_REDIRECT_URI",
        )
        diagnostics.extend(
            f"{name} is required" for name in required if not _value(name)
        )
        issuer = _value("UAGENT_OIDC_ISSUER")
        redirect = _value("UAGENT_OIDC_REDIRECT_URI")
        if issuer and urlparse(issuer).scheme not in {"http", "https"}:
            diagnostics.append("UAGENT_OIDC_ISSUER must be an HTTP(S) URL")
        if redirect and urlparse(redirect).scheme not in {"http", "https"}:
            diagnostics.append("UAGENT_OIDC_REDIRECT_URI must be an HTTP(S) URL")
        provider = "oidc"
    elif selected == "trusted_proxy":
        provider = "trusted proxy"
        try:
            TrustedProxyIdentityResolver()
        except IdentityConfigurationError as exc:
            diagnostics.append(str(exc))
    elif selected == "token":
        provider = "token registry"
        try:
            TokenIdentityResolver()
        except IdentityConfigurationError as exc:
            diagnostics.append(str(exc))
    else:
        provider = selected.replace("_", " ")
        registered, _ = enterprise_identity_adapter_state(selected)
        if not registered:
            diagnostics.append(f"{selected} verifier is not configured")

    configured = not diagnostics
    return AuthenticationStatus(
        selected,
        configured,
        "configured" if configured else "unconfigured",
        provider,
        tuple(diagnostics),
    )


__all__ = [
    "AuthenticationStatus",
    "authentication_configuration_fingerprint",
    "validate_authentication_configuration",
]

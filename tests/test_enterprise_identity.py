from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from uagent.runtime.enterprise_identity import (
    GroupPolicyAssignments,
    OAuthIdentityResolver,
    TokenIdentityResolver,
    TrustedProxyIdentityResolver,
    VerifiedEnterpriseIdentity,
    WindowsADIdentityResolver,
    opaque_principal_id,
    register_enterprise_identity_verifier,
)
from uagent.runtime.identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
    create_identity_resolver,
)


def _request(*, headers=None, host="127.0.0.1"):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=host),
    )


def test_opaque_principal_does_not_expose_subject_or_token():
    principal = opaque_principal_id("oauth", "https://provider.example", "user@example")
    assert principal.startswith("oauth:")
    assert "user@example" not in principal
    assert "provider.example" not in principal


def test_trusted_proxy_requires_source_boundary_and_configured_headers(monkeypatch):
    monkeypatch.setenv("UAGENT_TRUSTED_PROXY_IDENTITY_HEADER", "X-Verified-Subject")
    monkeypatch.setenv("UAGENT_TRUSTED_PROXY_ISSUER_HEADER", "X-Verified-Issuer")
    monkeypatch.setenv("UAGENT_TRUSTED_PROXY_CIDRS", "10.20.0.0/16,127.0.0.1/32")
    resolver = TrustedProxyIdentityResolver()
    headers = {
        "x-verified-subject": "S-1-5-21-stable",
        "x-verified-issuer": "corp-ad",
    }

    identity = resolver.resolve(_request(headers=headers, host="10.20.1.5"))
    assert identity.authn_kind == "trusted_proxy"
    assert identity.subject == "S-1-5-21-stable"
    assert "S-1-5-21-stable" not in identity.principal_id
    with pytest.raises(IdentityResolutionError, match="trusted proxy"):
        resolver.resolve(_request(headers=headers, host="203.0.113.4"))
    with pytest.raises(IdentityResolutionError, match="headers are missing"):
        resolver.resolve(_request(host="10.20.1.5"))


def test_trusted_proxy_missing_boundary_fails_at_factory(monkeypatch):
    monkeypatch.setenv("UAGENT_TRUSTED_PROXY_IDENTITY_HEADER", "X-Subject")
    monkeypatch.setenv("UAGENT_TRUSTED_PROXY_ISSUER_HEADER", "X-Issuer")
    monkeypatch.delenv("UAGENT_TRUSTED_PROXY_CIDRS", raising=False)
    with pytest.raises(IdentityConfigurationError, match="CIDR boundary"):
        create_identity_resolver("trusted_proxy")


def test_token_resolver_validates_hash_and_never_uses_token_as_owner(monkeypatch):
    credential = "secret-bearer-value"
    monkeypatch.setenv("UAGENT_TOKEN_NAMESPACE", "service-registry")
    monkeypatch.setenv(
        "UAGENT_TOKEN_IDENTITIES",
        json.dumps(
            [
                {
                    "token_sha256": hashlib.sha256(credential.encode()).hexdigest(),
                    "subject": "build-agent-7",
                    "display_name": "Build Agent",
                }
            ]
        ),
    )
    resolver = TokenIdentityResolver()

    identity = resolver.resolve(
        _request(headers={"Authorization": f"Bearer {credential}"})
    )
    assert identity.authn_kind == "token"
    assert identity.subject == "build-agent-7"
    assert credential not in identity.principal_id
    assert "build-agent-7" not in identity.principal_id
    with pytest.raises(IdentityResolutionError, match="invalid"):
        resolver.resolve(_request(headers={"Authorization": "Bearer wrong"}))


def test_oauth_and_windows_ad_accept_only_verified_adapter_output():
    oauth = OAuthIdentityResolver(
        lambda request: VerifiedEnterpriseIdentity(
            "github", "provider-user-42", "Octo", ("developers",)
        )
    )
    identity = oauth.resolve(object())
    assert identity.authn_kind == "oauth"
    assert identity.issuer == "github"
    assert identity.subject == "provider-user-42"

    invalid = WindowsADIdentityResolver(lambda request: "DOMAIN\\alice")
    with pytest.raises(IdentityResolutionError, match="invalid result"):
        invalid.resolve(object())


def test_registered_adapter_is_selected_without_fallback():
    register_enterprise_identity_verifier(
        "windows_ad",
        lambda request: VerifiedEnterpriseIdentity("corp-ad", "object-guid"),
    )
    try:
        identity = create_identity_resolver("windows_ad").resolve(object())
        assert identity.authn_kind == "windows_ad"
        assert identity.principal_id.startswith("windows_ad:")
    finally:
        register_enterprise_identity_verifier("windows_ad", None)

    with pytest.raises(IdentityConfigurationError, match="not configured"):
        create_identity_resolver("windows_ad")


def test_directory_groups_are_authorization_inputs_not_identity_keys():
    verified = VerifiedEnterpriseIdentity(
        "entra-tenant", "stable-object-id", groups=("UAG-Admins", "Developers")
    )
    identity = OAuthIdentityResolver(lambda request: verified).resolve(object())
    assignment = GroupPolicyAssignments(
        administrator=True,
        room_roles=(("development", "editor"),),
        project_ids=("agentcli",),
    )

    assert assignment.administrator is True
    assert "UAG-Admins" not in identity.principal_id
    assert "Developers" not in identity.principal_id

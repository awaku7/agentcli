from __future__ import annotations

import hashlib
import json

from uagent.runtime.auth_management import (
    authentication_configuration_fingerprint,
    validate_authentication_configuration,
)
from uagent.runtime.enterprise_identity import (
    VerifiedEnterpriseIdentity,
    register_enterprise_identity_verifier,
)


def test_oidc_validation_names_missing_settings_without_exposing_values(monkeypatch):
    secret = "do-not-return-this-secret"
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oidc")
    monkeypatch.setenv("UAGENT_OIDC_CLIENT_SECRET", secret)
    monkeypatch.delenv("UAGENT_OIDC_ISSUER", raising=False)
    monkeypatch.delenv("UAGENT_OIDC_CLIENT_ID", raising=False)
    monkeypatch.delenv("UAGENT_OIDC_REDIRECT_URI", raising=False)

    status = validate_authentication_configuration()
    rendered = json.dumps(status.public_dict())

    assert status.configured is False
    assert status.health == "unconfigured"
    assert "UAGENT_OIDC_ISSUER" in rendered
    assert secret not in rendered


def test_token_validation_does_not_expose_identity_configuration(monkeypatch):
    credential = "raw-token"
    subject = "private-service-account"
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "token")
    monkeypatch.setenv("UAGENT_TOKEN_NAMESPACE", "services")
    monkeypatch.setenv(
        "UAGENT_TOKEN_IDENTITIES",
        json.dumps(
            [
                {
                    "token_sha256": hashlib.sha256(credential.encode()).hexdigest(),
                    "subject": subject,
                }
            ]
        ),
    )

    status = validate_authentication_configuration()

    assert status.configured is True
    assert credential not in json.dumps(status.public_dict())
    assert subject not in json.dumps(status.public_dict())


def test_configuration_fingerprint_changes_with_security_configuration(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oidc")
    monkeypatch.setenv("UAGENT_OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("UAGENT_OIDC_CLIENT_ID", "client-a")
    monkeypatch.setenv("UAGENT_OIDC_REDIRECT_URI", "https://app.example/callback")
    before = authentication_configuration_fingerprint()

    monkeypatch.setenv("UAGENT_OIDC_CLIENT_ID", "client-b")

    assert authentication_configuration_fingerprint() != before


def test_oidc_secret_fingerprint_preserves_quoted_inner_whitespace(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oidc")
    monkeypatch.setenv("UAGENT_OIDC_CLIENT_SECRET", "secret")
    before = authentication_configuration_fingerprint()

    monkeypatch.setenv("UAGENT_OIDC_CLIENT_SECRET", "' secret '")

    assert authentication_configuration_fingerprint() != before


def test_oauth_secret_and_redirect_changes_update_fingerprint(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oauth")
    monkeypatch.setenv("UAGENT_OAUTH_PROVIDER", "provider")
    monkeypatch.setenv("UAGENT_OAUTH_CLIENT_ID", "client")
    monkeypatch.setenv("UAGENT_OAUTH_CLIENT_SECRET", "secret-a")
    monkeypatch.setenv("UAGENT_OAUTH_REDIRECT_URI", "https://app.example/callback-a")
    before = authentication_configuration_fingerprint()

    monkeypatch.setenv("UAGENT_OAUTH_CLIENT_SECRET", "secret-b")
    after_secret = authentication_configuration_fingerprint()
    monkeypatch.setenv("UAGENT_OAUTH_REDIRECT_URI", "https://app.example/callback-b")

    assert after_secret != before
    assert authentication_configuration_fingerprint() != after_secret


def test_oidc_health_uses_runtime_https_issuer_boundary(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oidc")
    monkeypatch.setenv("UAGENT_OIDC_CLIENT_ID", "client")
    monkeypatch.setenv("UAGENT_OIDC_REDIRECT_URI", "http://127.0.0.1/callback")

    for issuer in (
        "http://issuer.example",
        "https://user:password@issuer.example",
        "https://issuer.example#fragment",
    ):
        monkeypatch.setenv("UAGENT_OIDC_ISSUER", issuer)
        status = validate_authentication_configuration()
        assert status.configured is False
        assert "valid HTTPS URL" in " ".join(status.diagnostics)

    monkeypatch.setenv("UAGENT_OIDC_ISSUER", "https://issuer.example")
    assert validate_authentication_configuration().configured is True


def test_oidc_health_reports_malformed_bracketed_urls(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oidc")
    monkeypatch.setenv("UAGENT_OIDC_CLIENT_ID", "client")
    monkeypatch.setenv("UAGENT_OIDC_ISSUER", "https://[broken")
    monkeypatch.setenv("UAGENT_OIDC_REDIRECT_URI", "https://[broken")

    status = validate_authentication_configuration()

    assert status.configured is False
    assert "UAGENT_OIDC_ISSUER must be a valid HTTPS URL" in status.diagnostics
    assert "UAGENT_OIDC_REDIRECT_URI must be an HTTP(S) URL" in status.diagnostics


def test_oidc_health_rejects_invalid_session_limits(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "oidc")
    monkeypatch.setenv("UAGENT_OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("UAGENT_OIDC_CLIENT_ID", "client")
    monkeypatch.setenv("UAGENT_OIDC_REDIRECT_URI", "https://app.example/callback")

    for name in ("UAGENT_OIDC_SESSION_TTL", "UAGENT_OIDC_SESSION_MAX"):
        for invalid in ("invalid", "1.5", "0", "-1"):
            monkeypatch.setenv(name, invalid)
            status = validate_authentication_configuration()
            assert status.configured is False
            assert f"{name} must be a positive integer" in status.diagnostics
        monkeypatch.delenv(name, raising=False)

    assert validate_authentication_configuration().configured is True


def test_enterprise_adapter_registration_updates_health_and_revision(monkeypatch):
    monkeypatch.setenv("UAGENT_IDENTITY_MODE", "external")
    register_enterprise_identity_verifier("external", None)
    before = authentication_configuration_fingerprint()
    assert validate_authentication_configuration().configured is False

    register_enterprise_identity_verifier(
        "external", lambda request: VerifiedEnterpriseIdentity("host", "user")
    )
    try:
        assert validate_authentication_configuration().configured is True
        assert authentication_configuration_fingerprint() != before
    finally:
        register_enterprise_identity_verifier("external", None)

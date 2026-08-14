from __future__ import annotations

import pytest

from uagent.auth.oauth_common import OAuthMetadataTrustError, validate_endpoint_trust
from uagent.auth.pkce import code_challenge_s256, generate_code_verifier
from uagent.providers.provider_caps import DEFAULT_PROVIDER_REGISTRY
from uagent.runtime.logging_setup import _safe_fields
from uagent.tools.tool_policy import SideEffect, policy_for


def test_shared_pkce_and_oauth_trust_helpers() -> None:
    verifier = generate_code_verifier()
    assert len(code_challenge_s256(verifier)) > 20
    assert validate_endpoint_trust("https://auth.example/token", "https://auth.example")
    with pytest.raises(OAuthMetadataTrustError):
        validate_endpoint_trust("https://evil.example/token", "https://auth.example")


def test_policy_has_resource_key_and_unknown_is_conservative() -> None:
    assert policy_for("delete_file", {"path": "a.txt"}).resource_key == "delete_file:path:a.txt"
    assert policy_for("future_tool").side_effect is SideEffect.IDEMPOTENT_WRITE
    assert not DEFAULT_PROVIDER_REGISTRY.resolve("future").supports_tools


def test_structured_log_fields_redact_secrets() -> None:
    result = _safe_fields({"event": "x", "access_token": "secret", "locale": "ja"})
    assert result["access_token"] == "[REDACTED]"
    assert result["locale"] == "ja"

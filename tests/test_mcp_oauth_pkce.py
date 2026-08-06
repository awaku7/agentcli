from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from uagent.tools.mcp.oauth_pkce import (
    build_authorization_url,
    code_challenge_s256,
    generate_code_verifier,
    generate_state,
    validate_state,
)


def test_pkce_verifier_challenge_and_state() -> None:
    verifier = generate_code_verifier()
    challenge = code_challenge_s256(verifier)
    state = generate_state()

    assert 43 <= len(verifier) <= 128
    assert challenge
    assert validate_state(state, state)
    assert not validate_state(state, state + "x")


def test_authorization_url_contains_pkce_and_resource() -> None:
    verifier = generate_code_verifier()
    url = build_authorization_url(
        "https://auth.example/authorize",
        client_id="uag-client",
        redirect_uri="http://127.0.0.1/callback",
        scope="mcp:read mcp:write",
        state="state-1",
        code_challenge=code_challenge_s256(verifier),
        resource="https://mcp.example/mcp",
    )
    query = parse_qs(urlparse(url).query)
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["resource"] == ["https://mcp.example/mcp"]


def test_pkce_rejects_invalid_lengths() -> None:
    with pytest.raises(ValueError):
        generate_code_verifier(42)
    with pytest.raises(ValueError):
        code_challenge_s256("short")

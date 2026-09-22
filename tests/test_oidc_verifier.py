"""Only verified OIDC ID tokens may produce a principal."""

from __future__ import annotations

import json
import time

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from uagent.auth import oidc_verifier as oidc
from uagent.runtime.identity_context import IdentityResolutionError


@pytest.fixture
def signing_material():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "key-1"
    return private_key, {"keys": [jwk]}


@pytest.fixture
def metadata():
    return oidc.OIDCProviderMetadata(
        issuer="https://identity.example/tenant",
        authorization_endpoint="https://identity.example/authorize",
        token_endpoint="https://identity.example/token",
        jwks_uri="https://identity.example/keys",
    )


def signed_token(private_key, metadata, **changes):
    claims = {
        "iss": metadata.issuer,
        "sub": "stable-subject",
        "aud": "uag-client",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "nonce": "expected-nonce",
        "name": "Initial Name",
    }
    claims.update(changes)
    return jwt.encode(
        claims, private_key, algorithm="RS256", headers={"kid": "key-1"}
    )


def verify(token, metadata, jwks, **options):
    return oidc.verify_id_token(
        token,
        metadata=metadata,
        jwks=jwks,
        client_id=options.get("client_id", "uag-client"),
        nonce=options.get("nonce", "expected-nonce"),
    )


def test_verified_subject_is_stable_across_display_changes(
    signing_material, metadata
):
    private_key, jwks = signing_material
    a = verify(signed_token(private_key, metadata), metadata, jwks)
    b = verify(signed_token(private_key, metadata, name="New Name"), metadata, jwks)
    assert a.principal_id == b.principal_id
    assert a.principal_id.startswith("oidc:")
    assert a.display_name != b.display_name
    assert a.principal_id != a.subject


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://other.example/tenant"},
        {"aud": "other-client"},
        {"exp": 1},
        {"nonce": "wrong-nonce"},
        {"sub": ""},
        {"aud": ["uag-client", "other-client"]},
        {"azp": "other-client"},
    ],
)
def test_invalid_claims_do_not_resolve(signing_material, metadata, changes):
    private_key, jwks = signing_material
    with pytest.raises(IdentityResolutionError):
        verify(signed_token(private_key, metadata, **changes), metadata, jwks)


def test_invalid_signature_and_algorithm_do_not_resolve(signing_material, metadata):
    private_key, jwks = signing_material
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(IdentityResolutionError):
        verify(signed_token(other_key, metadata), metadata, jwks)
    hs_token = jwt.encode(
        {"iss": metadata.issuer}, "secret", algorithm="HS256", headers={"kid": "key-1"}
    )
    with pytest.raises(IdentityResolutionError):
        verify(hs_token, metadata, jwks)


def test_discovery_requires_exact_issuer_and_https(monkeypatch, metadata):
    document = {
        "issuer": metadata.issuer,
        "authorization_endpoint": metadata.authorization_endpoint,
        "token_endpoint": metadata.token_endpoint,
        "jwks_uri": metadata.jwks_uri,
    }
    monkeypatch.setattr(oidc, "_get_json", lambda url: document)
    assert oidc.discover_provider(metadata.issuer) == metadata

    document["issuer"] = "https://identity.example/other"
    with pytest.raises(IdentityResolutionError, match="issuer mismatch"):
        oidc.discover_provider(metadata.issuer)
    with pytest.raises(IdentityResolutionError, match="invalid OIDC issuer"):
        oidc.discover_provider("http://identity.example/tenant")

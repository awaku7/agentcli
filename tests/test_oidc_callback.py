"""OIDC code callbacks are single-use and verify the returned ID token."""

from __future__ import annotations

import asyncio
import json
import time

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from uagent.auth.oidc_callback import complete_authorization_callback
from uagent.auth.oidc_transactions import OIDCTransactionStore
from uagent.auth.oidc_verifier import OIDCProviderMetadata
from uagent.runtime.identity_context import IdentityResolutionError


class FakeResponse:
    def __init__(self, payload, *, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("token endpoint error")

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    async def post(self, url, *, data, headers):
        self.requests.append((url, data, headers))
        return self.response


@pytest.fixture
def metadata():
    return OIDCProviderMetadata(
        issuer="https://identity.example/tenant",
        authorization_endpoint="https://identity.example/authorize",
        token_endpoint="https://identity.example/token",
        jwks_uri="https://identity.example/keys",
    )


@pytest.fixture
def signing_material():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "key-1"
    return private_key, {"keys": [jwk]}


def make_token(private_key, metadata, *, nonce):
    return jwt.encode(
        {
            "iss": metadata.issuer,
            "sub": "stable-subject",
            "aud": "uag-client",
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "nonce": nonce,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )


def test_callback_exchanges_code_with_transaction_verifier_and_nonce(
    metadata, signing_material
):
    private_key, jwks = signing_material
    store = OIDCTransactionStore()
    transaction = store.begin("browser-A")
    token = make_token(private_key, metadata, nonce=transaction.nonce)
    client = FakeClient(FakeResponse({"id_token": token}))

    identity = asyncio.run(
        complete_authorization_callback(
            store=store,
            metadata=metadata,
            state=transaction.state,
            browser_binding="browser-A",
            code="authorization-code",
            client_id="uag-client",
            redirect_uri="https://uag.example/auth/callback",
            http_client=client,
            jwks=jwks,
        )
    )

    assert identity.authenticated
    assert identity.authn_kind == "oidc"
    assert identity.subject == "stable-subject"
    url, data, headers = client.requests[0]
    assert url == metadata.token_endpoint
    assert data["code_verifier"] == transaction.code_verifier
    assert data["code"] == "authorization-code"
    assert "client_secret" not in data
    assert headers == {"Accept": "application/json"}

    with pytest.raises(IdentityResolutionError, match="authorization callback"):
        asyncio.run(
            complete_authorization_callback(
            store=store,
            metadata=metadata,
            state=transaction.state,
            browser_binding="browser-A",
            code="authorization-code",
            client_id="uag-client",
            redirect_uri="https://uag.example/auth/callback",
            http_client=client,
            jwks=jwks,
        )
    )


def test_callback_rejects_wrong_browser_before_token_exchange(
    metadata, signing_material
):
    private_key, jwks = signing_material
    store = OIDCTransactionStore()
    transaction = store.begin("browser-A")
    token = make_token(private_key, metadata, nonce=transaction.nonce)
    client = FakeClient(FakeResponse({"id_token": token}))

    with pytest.raises(IdentityResolutionError, match="authorization callback"):
        asyncio.run(
            complete_authorization_callback(
            store=store,
            metadata=metadata,
            state=transaction.state,
            browser_binding="browser-B",
            code="authorization-code",
            client_id="uag-client",
            redirect_uri="https://uag.example/auth/callback",
            http_client=client,
            jwks=jwks,
        )
    )

    assert client.requests == []


def test_callback_rejects_id_token_with_wrong_nonce(metadata, signing_material):
    private_key, jwks = signing_material
    store = OIDCTransactionStore()
    transaction = store.begin("browser-A")
    token = make_token(private_key, metadata, nonce="wrong-nonce")
    client = FakeClient(FakeResponse({"id_token": token}))

    with pytest.raises(IdentityResolutionError, match="nonce mismatch"):
        asyncio.run(
            complete_authorization_callback(
            store=store,
            metadata=metadata,
            state=transaction.state,
            browser_binding="browser-A",
            code="authorization-code",
            client_id="uag-client",
            redirect_uri="https://uag.example/auth/callback",
            http_client=client,
            jwks=jwks,
        )
    )


def test_callback_rejects_missing_id_token(metadata):
    store = OIDCTransactionStore()
    transaction = store.begin("browser-A")
    client = FakeClient(FakeResponse({"access_token": "not-an-identity"}))

    with pytest.raises(IdentityResolutionError, match="missing ID token"):
        asyncio.run(
            complete_authorization_callback(
            store=store,
            metadata=metadata,
            state=transaction.state,
            browser_binding="browser-A",
            code="authorization-code",
            client_id="uag-client",
            redirect_uri="https://uag.example/auth/callback",
            http_client=client,
            jwks={"keys": []},
        )
    )


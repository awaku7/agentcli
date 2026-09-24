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
        self.graph_responses = []
        self.graph_requests = []

    async def post(self, url, *, data, headers):
        self.requests.append((url, data, headers))
        return self.response

    async def get(self, url, *, headers, follow_redirects, timeout):
        self.graph_requests.append((url, headers, follow_redirects, timeout))
        if not self.graph_responses:
            raise AssertionError("unexpected Graph request")
        return self.graph_responses.pop(0)


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


def make_token(private_key, metadata, *, nonce, extra_claims=None):
    claims = {
        "iss": metadata.issuer,
        "sub": "stable-subject",
        "aud": "uag-client",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "nonce": nonce,
    }
    claims.update(extra_claims or {})
    return jwt.encode(
        claims,
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


def test_entra_group_overage_is_resolved_from_bounded_graph_pages(
    signing_material, monkeypatch
):
    private_key, jwks = signing_material
    metadata = OIDCProviderMetadata(
        issuer="https://login.microsoftonline.com/tenant/v2.0",
        authorization_endpoint="https://login.microsoftonline.com/authorize",
        token_endpoint="https://login.microsoftonline.com/token",
        jwks_uri="https://login.microsoftonline.com/keys",
    )
    transaction_store = OIDCTransactionStore()
    transaction = transaction_store.begin("browser-A")
    token = make_token(
        private_key,
        metadata,
        nonce=transaction.nonce,
        extra_claims={"_claim_names": {"groups": "src1"}},
    )
    client = FakeClient(
        FakeResponse(
            {
                "id_token": token,
                "access_token": "ephemeral-graph-token",
                "token_type": "Bearer",
            }
        )
    )
    client.graph_responses = [
        FakeResponse(
            {
                "value": [{"id": "group-b"}],
                "@odata.nextLink": (
                    "https://graph.microsoft.com/v1.0/me/transitiveMemberOf/"
                    "microsoft.graph.group?$skiptoken=next"
                ),
            }
        ),
        FakeResponse({"value": [{"id": "group-a"}, {"id": "group-b"}]}),
    ]
    monkeypatch.setenv("UAGENT_OIDC_GRAPH_SCOPE", "GroupMember.Read.All")

    identity = asyncio.run(
        complete_authorization_callback(
            store=transaction_store,
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

    assert identity.groups == ("group-a", "group-b")
    assert len(client.graph_requests) == 2
    assert all(
        request[1]["Authorization"] == "Bearer ephemeral-graph-token"
        and request[2] is False
        for request in client.graph_requests
    )
    assert "ephemeral-graph-token" not in repr(identity)


def test_entra_group_overage_rejects_untrusted_graph_pagination_url(
    signing_material, monkeypatch
):
    private_key, jwks = signing_material
    metadata = OIDCProviderMetadata(
        issuer="https://login.microsoftonline.com/tenant/v2.0",
        authorization_endpoint="https://login.microsoftonline.com/authorize",
        token_endpoint="https://login.microsoftonline.com/token",
        jwks_uri="https://login.microsoftonline.com/keys",
    )
    transaction_store = OIDCTransactionStore()
    transaction = transaction_store.begin("browser-A")
    token = make_token(
        private_key,
        metadata,
        nonce=transaction.nonce,
        extra_claims={"hasgroups": True},
    )
    client = FakeClient(
        FakeResponse(
            {
                "id_token": token,
                "access_token": "ephemeral-graph-token",
                "token_type": "Bearer",
            }
        )
    )
    client.graph_responses = [
        FakeResponse(
            {
                "value": [],
                "@odata.nextLink": "https://attacker.example/steal-token",
            }
        )
    ]
    monkeypatch.setenv("UAGENT_OIDC_GRAPH_SCOPE", "GroupMember.Read.All")

    with pytest.raises(IdentityResolutionError, match="unsafe pagination URL"):
        asyncio.run(
            complete_authorization_callback(
                store=transaction_store,
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

    assert len(client.graph_requests) == 1
    assert client.graph_requests[0][0].startswith("https://graph.microsoft.com/")

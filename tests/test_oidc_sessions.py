from __future__ import annotations

import pytest

from uagent.auth.oidc_sessions import OIDCSessionStore
from uagent.runtime.identity_context import IdentityContext


def test_oidc_session_is_opaque_single_store_token() -> None:
    identity = IdentityContext("oidc:user", True, "oidc")
    store = OIDCSessionStore()
    token = store.create(identity)

    assert token
    assert token != identity.principal_id
    assert store.resolve(token) == identity
    assert store.resolve("wrong-token") is None


def test_oidc_session_expiry_and_revoke() -> None:
    now = [100.0]
    store = OIDCSessionStore(clock=lambda: now[0], ttl_seconds=10)
    token = store.create(IdentityContext("oidc:user", True, "oidc"))

    now[0] = 109.9
    assert store.resolve(token) is not None
    now[0] = 110.0
    assert store.resolve(token) is None

    token = store.create(IdentityContext("oidc:user", True, "oidc"))
    store.revoke(token)
    assert store.resolve(token) is None


def test_oidc_session_requires_authenticated_identity() -> None:
    store = OIDCSessionStore()
    with pytest.raises(ValueError, match="authenticated"):
        store.create(IdentityContext("anonymous", False, "oidc"))

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


def test_oidc_sessions_are_invalidated_when_authentication_config_changes() -> None:
    revision = ["revision-1"]
    store = OIDCSessionStore(configuration_fingerprint=lambda: revision[0])
    token = store.create(IdentityContext("oidc:user", True, "oidc"))

    assert store.active_count() == 1
    revision[0] = "revision-2"
    assert store.resolve(token) is None
    assert store.active_count() == 0


def test_oidc_session_store_can_revoke_all_sessions() -> None:
    store = OIDCSessionStore(configuration_fingerprint=lambda: "stable")
    store.create(IdentityContext("oidc:user-a", True, "oidc"))
    store.create(IdentityContext("oidc:user-b", True, "oidc"))

    assert store.revoke_all() == 2
    assert store.active_count() == 0


def test_stale_sessions_do_not_count_toward_capacity() -> None:
    revision = ["revision-1"]
    store = OIDCSessionStore(
        max_sessions=1, configuration_fingerprint=lambda: revision[0]
    )
    store.create(IdentityContext("oidc:user-a", True, "oidc"))

    revision[0] = "revision-2"
    assert store.active_count() == 0
    token = store.create(IdentityContext("oidc:user-b", True, "oidc"))

    assert store.resolve(token) == IdentityContext("oidc:user-b", True, "oidc")


def test_new_sessions_use_rotated_ttl_and_capacity() -> None:
    now = [100.0]
    revision = ["revision-1"]
    ttl = [10]
    capacity = [1]
    store = OIDCSessionStore(
        clock=lambda: now[0],
        configuration_fingerprint=lambda: revision[0],
        ttl_seconds_provider=lambda: ttl[0],
        max_sessions_provider=lambda: capacity[0],
    )
    store.create(IdentityContext("oidc:user-a", True, "oidc"))

    revision[0] = "revision-2"
    ttl[0] = 20
    capacity[0] = 2
    token = store.create(IdentityContext("oidc:user-b", True, "oidc"))

    now[0] = 119.9
    assert store.resolve(token) is not None
    now[0] = 120.0
    assert store.resolve(token) is None

"""OIDC authorization transactions enforce browser binding, expiry, and replay."""

from __future__ import annotations

import pytest

from uagent.auth.oidc_transactions import OIDCTransactionStore
from uagent.auth.pkce import code_challenge_s256


def test_transaction_has_independent_state_nonce_and_s256_challenge():
    store = OIDCTransactionStore()
    first = store.begin("browser-A")
    second = store.begin("browser-A")

    assert first.state != second.state
    assert first.nonce != second.nonce
    assert first.code_challenge == code_challenge_s256(first.code_verifier)
    assert store.consume(state=first.state, browser_binding="browser-A") == first
    with pytest.raises(ValueError, match="replayed"):
        store.consume(state=first.state, browser_binding="browser-A")


def test_callback_from_another_browser_cannot_consume_transaction():
    store = OIDCTransactionStore()
    transaction = store.begin("browser-A")

    with pytest.raises(ValueError, match="binding mismatch"):
        store.consume(state=transaction.state, browser_binding="browser-B")
    assert store.consume(state=transaction.state, browser_binding="browser-A")


def test_expired_transaction_is_rejected_and_capacity_is_reclaimed():
    now = [100.0]
    store = OIDCTransactionStore(ttl_seconds=30, max_pending=1, clock=lambda: now[0])
    expired = store.begin("browser-A")
    with pytest.raises(RuntimeError, match="capacity"):
        store.begin("browser-B")
    now[0] = 130.0
    with pytest.raises(ValueError, match="expired"):
        store.consume(state=expired.state, browser_binding="browser-A")
    assert store.begin("browser-B").state != expired.state


def test_missing_browser_binding_and_state_fail_closed():
    store = OIDCTransactionStore()
    with pytest.raises(ValueError, match="browser binding"):
        store.begin("")
    transaction = store.begin("browser-A")
    with pytest.raises(ValueError, match="required"):
        store.consume(state=transaction.state, browser_binding="")
    with pytest.raises(ValueError, match="required"):
        store.consume(state="", browser_binding="browser-A")

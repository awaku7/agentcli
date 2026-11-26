"""BLE -> Nostr DM fallback in pybitchat_shared.enqueue_send.

A BLE DM addressed to a peer who is not on the mesh right now goes
out over Nostr instead, when that peer is paired with a linked
Nostr key. Peers who are present, unpaired peers, and explicit
via choices keep the existing behaviour.
"""

from __future__ import annotations

import queue

import pytest
from bitchat_protocol import peer_id_from_noise_key

from uagent import bitchat_pairing
from uagent.bitchat_pairing import SQLiteBitchatPairingStore
from uagent.tools import pybitchat_shared as pbs

NOISE_A = "aa" * 32
NOISE_B = "bb" * 32
NOSTR_A = "cc" * 32
PEER_A = peer_id_from_noise_key(bytes.fromhex(NOISE_A))
PEER_B = peer_id_from_noise_key(bytes.fromhex(NOISE_B))


class _FakeNostr:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str | None]] = []
        self.text_sent: list[str] = []

    def nostr_send_kind1059(self, text, recipient=None):
        self.sent.append((text, recipient))
        return {"ok": True, "via": "nostr", "kind": 1059}

    def nostr_send_text(self, text):
        self.text_sent.append(text)
        return {"ok": True}

    def nostr_send_geohash(self, text, geohash):
        return {"ok": True}


@pytest.fixture()
def node(tmp_path, monkeypatch):
    """Shared-module state: Nostr running, nobody heard on the mesh."""
    db = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(
        bitchat_pairing,
        "open_bitchat_pairing_store",
        lambda: SQLiteBitchatPairingStore(db),
    )
    fake = _FakeNostr()
    outbound: queue.Queue = queue.Queue()
    displayed: list[str] = []
    monkeypatch.setattr(pbs, "_NOSTR", fake)
    monkeypatch.setattr(pbs, "_NOSTR_RUNNING", True)
    monkeypatch.setattr(pbs, "_PEER_NOISE_KEYS", {})
    monkeypatch.setattr(pbs, "_PEER_NICKNAMES", {})
    monkeypatch.setattr(pbs, "_OUTBOUND_QUEUE", outbound)
    monkeypatch.setattr(pbs, "_notify_display", displayed.append)
    return db, fake, outbound, displayed


def _pair_with_nostr(db, noise=NOISE_A, nostr=NOSTR_A) -> None:
    with SQLiteBitchatPairingStore(db) as store:
        store.pair(noise, "phone", approved=True)
        store.link_nostr(noise, nostr, approved=True)


def test_absent_paired_peer_dm_goes_via_nostr(node) -> None:
    db, fake, outbound, displayed = node
    _pair_with_nostr(db)

    pbs.enqueue_send("text", "hello there", recipient=PEER_A)

    assert fake.sent == [("hello there", NOSTR_A)]
    assert outbound.empty()
    assert any("Nostr" in line for line in displayed)


def test_present_peer_dm_stays_on_ble(node, monkeypatch) -> None:
    db, fake, outbound, _displayed = node
    _pair_with_nostr(db)
    monkeypatch.setattr(pbs, "_PEER_NOISE_KEYS", {PEER_A: NOISE_A})

    pbs.enqueue_send("text", "hello there", recipient=PEER_A)

    assert fake.sent == []
    assert not outbound.empty()


def test_absent_unpaired_peer_dm_stays_on_ble(node) -> None:
    _db, fake, outbound, _displayed = node

    pbs.enqueue_send("text", "hello there", recipient=PEER_B)

    assert fake.sent == []
    assert not outbound.empty()


def test_absent_paired_peer_without_nostr_link_stays_on_ble(node) -> None:
    db, fake, outbound, _displayed = node
    with SQLiteBitchatPairingStore(db) as store:
        store.pair(NOISE_A, "phone", approved=True)

    pbs.enqueue_send("text", "hello there", recipient=PEER_A)

    assert fake.sent == []
    assert not outbound.empty()


def test_fallback_requires_nostr_running(node, monkeypatch) -> None:
    db, fake, outbound, _displayed = node
    _pair_with_nostr(db)
    monkeypatch.setattr(pbs, "_NOSTR_RUNNING", False)

    pbs.enqueue_send("text", "hello there", recipient=PEER_A)

    assert fake.sent == []
    assert not outbound.empty()


def test_explicit_via_and_plain_sends_are_not_rerouted(node) -> None:
    db, fake, outbound, _displayed = node
    _pair_with_nostr(db)

    # via="both" already includes Nostr through the normal path; the
    # fallback must not turn it into a kind-1059 DM or suppress BLE.
    pbs.enqueue_send("text", "hello there", recipient=PEER_A, via="both")
    assert fake.sent == []
    assert fake.text_sent == ["hello there"]
    assert not outbound.empty()

    while not outbound.empty():
        outbound.get_nowait()

    # Plain (unencrypted) DMs have no paired identity to reroute by.
    pbs.enqueue_send("text", "hello there", recipient=PEER_A, plain=True)
    assert fake.sent == []
    assert not outbound.empty()

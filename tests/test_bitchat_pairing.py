"""Tests for the BitChat pairing registry and llm-mode DM gating.

The registry (bitchat_pairing.py) is what authorizes a peer's DMs to
reach the LLM in :bitchat llm mode: BLE peers by their verified Noise
key, Nostr peers by an explicit :nostr pair or a linked Nostr key.
"""

from __future__ import annotations

import queue

import pytest

from uagent.bitchat_pairing import SQLiteBitchatPairingStore

NOISE_A = "aa" * 32
NOISE_B = "bb" * 32
NOSTR_A = "cc" * 32


@pytest.fixture()
def store(tmp_path):
    with SQLiteBitchatPairingStore(tmp_path / "pairings.sqlite3") as s:
        yield s


def test_pair_requires_approval(store) -> None:
    with pytest.raises(PermissionError):
        store.pair(NOISE_A, "phone")
    assert not store.is_authorized_noise(NOISE_A)


def test_pair_and_authorize_noise(store) -> None:
    record = store.pair(NOISE_A, "phone", approved=True)
    assert record.active
    assert record.label == "phone"
    assert store.is_authorized_noise(NOISE_A)
    assert not store.is_authorized_noise(NOISE_B)


def test_pair_rejects_bad_keys(store) -> None:
    with pytest.raises(ValueError):
        store.pair("not-hex", "x", approved=True)
    with pytest.raises(ValueError):
        store.pair("ab" * 10, "x", approved=True)
    assert not store.is_authorized_noise("not-hex")


def test_link_nostr_authorizes_nostr_dm(store) -> None:
    store.pair(NOISE_A, "phone", approved=True)
    assert not store.is_authorized_nostr(NOSTR_A)
    record = store.link_nostr(NOISE_A, NOSTR_A, approved=True)
    assert record.nostr_key == NOSTR_A
    assert store.is_authorized_nostr(NOSTR_A)


def test_link_requires_existing_pairing_and_approval(store) -> None:
    with pytest.raises(PermissionError):
        store.link_nostr(NOISE_A, NOSTR_A)
    with pytest.raises(ValueError):
        store.link_nostr(NOISE_A, NOSTR_A, approved=True)


def test_revoke_blocks_both_transports(store) -> None:
    store.pair(NOISE_A, "phone", approved=True)
    store.link_nostr(NOISE_A, NOSTR_A, approved=True)
    assert store.revoke(NOISE_A)
    assert not store.is_authorized_noise(NOISE_A)
    assert not store.is_authorized_nostr(NOSTR_A)
    assert not store.revoke(NOISE_A)
    # Re-pairing reactivates the record but drops the old Nostr link.
    store.pair(NOISE_A, "phone", approved=True)
    assert store.is_authorized_noise(NOISE_A)
    assert not store.is_authorized_nostr(NOSTR_A)


def test_list_devices(store) -> None:
    store.pair(NOISE_A, "a", approved=True)
    store.pair(NOISE_B, "b", approved=True)
    store.revoke(NOISE_B)
    active = store.list_devices()
    assert [r.noise_key for r in active] == [NOISE_A]
    everyone = store.list_devices(include_revoked=True)
    assert len(everyone) == 2


def test_favorite_claim_links_only_empty_slot(store) -> None:
    # Unpaired peers cannot self-link.
    assert store.apply_favorite_claim(NOISE_A, NOSTR_A, favorited=True) == "unpaired"
    store.pair(NOISE_A, "phone", approved=True)
    assert store.apply_favorite_claim(NOISE_A, NOSTR_A, favorited=True) == "linked"
    assert store.is_authorized_nostr(NOSTR_A)
    assert store.apply_favorite_claim(NOISE_A, NOSTR_A, favorited=True) == "already"
    # A different claimed key never overwrites the existing link.
    assert store.apply_favorite_claim(NOISE_A, NOISE_B, favorited=True) == "conflict"
    assert store.is_authorized_nostr(NOSTR_A)
    assert not store.is_authorized_nostr(NOISE_B)


def test_favorite_unclaim_unlinks_only_on_match(store) -> None:
    store.pair(NOISE_A, "phone", approved=True)
    store.link_nostr(NOISE_A, NOSTR_A, approved=True)
    assert store.apply_favorite_claim(NOISE_A, NOISE_B, favorited=False) == "noop"
    assert store.is_authorized_nostr(NOSTR_A)
    assert store.apply_favorite_claim(NOISE_A, NOSTR_A, favorited=False) == "unlinked"
    assert not store.is_authorized_nostr(NOSTR_A)


# ---- llm-mode gating in pybitchat_shared ------------------------------------


@pytest.fixture()
def llm_mode(monkeypatch):
    from uagent.tools import pybitchat_shared as pbs

    events: queue.Queue = queue.Queue()
    monkeypatch.setattr(pbs, "_CHAT_MODE", "llm")
    pbs.set_llm_event_queue(events)
    yield pbs, events
    pbs.set_llm_event_queue(None)


def test_nostr_dm_injected_only_when_paired(llm_mode, monkeypatch) -> None:
    pbs, events = llm_mode
    monkeypatch.setattr(pbs, "_is_paired_nostr_peer", lambda key: False)
    pbs._on_nostr_dm(NOSTR_A, "hello")
    assert events.empty()

    monkeypatch.setattr(pbs, "_is_paired_nostr_peer", lambda key: key == NOSTR_A)
    pbs._on_nostr_dm(NOSTR_A, "hello")
    event = events.get_nowait()
    assert event["src"] == "bitchat"
    assert "hello" in event["text"]
    assert event["reply_route"] == {"via": "nostr", "peer": NOSTR_A}


def test_public_nostr_message_never_injected(llm_mode, monkeypatch) -> None:
    pbs, events = llm_mode
    monkeypatch.setattr(pbs, "_is_paired_nostr_peer", lambda key: True)
    pbs._on_nostr_message("someone", "channel chatter", 20000)
    pbs._on_nostr_message("someone", "public post", 1)
    assert events.empty()


def test_reply_goes_back_as_dm(llm_mode, monkeypatch) -> None:
    pbs, _events = llm_mode
    sent: list[tuple] = []
    monkeypatch.setattr(pbs, "_RUNNING", True)
    monkeypatch.setattr(
        pbs,
        "enqueue_send",
        lambda type_, payload, recipient=None, via="ble", plain=False: sent.append(
            (type_, payload, recipient, via)
        ),
    )
    pbs.reply_to_bitchat_dm("answer", {"via": "nostr", "peer": NOSTR_A})
    pbs.reply_to_bitchat_dm("answer", {"via": "ble", "peer": "0123456789abcdef"})
    pbs.reply_to_bitchat_dm("answer", None)
    assert sent == [
        ("text", "answer", NOSTR_A, "nostr"),
        ("text", "answer", "0123456789abcdef", "ble"),
    ]


def test_paired_checks_read_the_registries(tmp_path, monkeypatch) -> None:
    from uagent import bitchat_pairing
    from uagent.tools import pybitchat_shared as pbs

    db = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(
        bitchat_pairing,
        "open_bitchat_pairing_store",
        lambda: SQLiteBitchatPairingStore(db),
    )
    with SQLiteBitchatPairingStore(db) as s:
        s.pair(NOISE_A, "phone", approved=True)
        s.link_nostr(NOISE_A, NOSTR_A, approved=True)
    assert pbs._is_paired_noise_peer(NOISE_A)
    assert not pbs._is_paired_noise_peer(NOISE_B)
    assert pbs._is_paired_nostr_peer(NOSTR_A)


def test_favorite_claim_over_noise_links_nostr(tmp_path, monkeypatch) -> None:
    from uagent import bitchat_pairing
    from uagent.tools import pybitchat_shared as pbs
    from uagent.tools.nostr_transport import encode_npub

    # A real secp256k1 x-only key (the generator point's x coordinate);
    # npub decoding validates that the key is on the curve.
    nostr_key = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    db = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(
        bitchat_pairing,
        "open_bitchat_pairing_store",
        lambda: SQLiteBitchatPairingStore(db),
    )
    with SQLiteBitchatPairingStore(db) as s:
        s.pair(NOISE_A, "phone", approved=True)
    claim = f"[FAVORITED]:{encode_npub(nostr_key)}"
    assert pbs._handle_favorite_claim(NOISE_A, "phone", claim)
    assert pbs._is_paired_nostr_peer(nostr_key)
    # Ordinary chat text is not a claim.
    assert not pbs._handle_favorite_claim(NOISE_A, "phone", "hello there")


def test_nostr_side_favorite_claim_never_injected(llm_mode, monkeypatch) -> None:
    pbs, events = llm_mode
    monkeypatch.setattr(pbs, "_is_paired_nostr_peer", lambda key: True)
    pbs._on_nostr_dm(
        NOSTR_A,
        "[FAVORITED]:npub1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq0qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq",
    )
    assert events.empty()


def test_nostr_receipts_never_injected(llm_mode, monkeypatch) -> None:
    pbs, events = llm_mode
    monkeypatch.setattr(pbs, "_is_paired_nostr_peer", lambda key: True)
    # A paired client acknowledging a reply must not start another round.
    pbs._on_nostr_dm(NOSTR_A, "/receipt read 0123456789abcdef")
    pbs._on_nostr_dm(NOSTR_A, "/read 0123456789abcdef")
    assert events.empty()
    # Ordinary text that merely mentions receipts still goes through.
    pbs._on_nostr_dm(NOSTR_A, "please read the report")
    assert not events.empty()

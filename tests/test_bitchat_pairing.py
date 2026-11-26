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


def test_pairing_binding_defaults_to_attach_and_can_switch(store) -> None:
    record = store.pair(NOISE_A, "phone", approved=True)
    assert record.binding == "attach"
    assert record.room_session_id is None
    assert store.set_binding(NOISE_A, "room")
    record = store.record_for(NOISE_A)
    assert record is not None and record.binding == "room"
    with pytest.raises(ValueError):
        store.set_binding(NOISE_A, "sideways")
    assert not store.set_binding(NOISE_B, "room")


def test_room_session_id_sticks_and_repairing_resets(store) -> None:
    store.pair(NOISE_A, "phone", approved=True, binding="room")
    assert store.ensure_room_session_id(NOISE_A, "sess-first") == "sess-first"
    assert store.ensure_room_session_id(NOISE_A, "sess-other") == "sess-first"
    store.link_nostr(NOISE_A, NOSTR_A, approved=True)
    by_nostr = store.record_for_nostr(NOSTR_A)
    assert by_nostr is not None and by_nostr.binding == "room"
    assert by_nostr.room_session_id == "sess-first"
    store.revoke(NOISE_A)
    record = store.pair(NOISE_A, "phone", approved=True)
    assert record.binding == "attach"
    assert record.room_session_id is None
    assert record.nostr_key is None


def test_bitchat_pairing_store_migrates_a_pre_binding_database(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "pairings.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE bitchat_pairings ("
        "noise_key TEXT PRIMARY KEY, nostr_key TEXT, label TEXT NOT NULL, "
        "paired_at INTEGER NOT NULL, revoked_at INTEGER)"
    )
    connection.execute(
        "INSERT INTO bitchat_pairings VALUES (?, NULL, 'old phone', 1, NULL)",
        (NOISE_A,),
    )
    connection.commit()
    connection.close()
    with SQLiteBitchatPairingStore(path) as reopened:
        record = reopened.record_for(NOISE_A)
        assert record is not None
        assert record.binding == "attach"
        assert record.room_session_id is None


def test_chat_room_descriptor_for_room_bound_peers(tmp_path, monkeypatch) -> None:
    import contextlib

    from cryptography.hazmat.primitives.asymmetric import ec

    from uagent.tools import pybitchat_shared as pbs

    bitchat_db = tmp_path / "bitchat.sqlite3"

    @contextlib.contextmanager
    def _open():
        with SQLiteBitchatPairingStore(bitchat_db) as s:
            yield s

    monkeypatch.setattr("uagent.bitchat_pairing.open_bitchat_pairing_store", _open)
    with SQLiteBitchatPairingStore(bitchat_db) as s:
        s.pair(NOISE_A, "peer", approved=True, binding="room")
        s.pair(NOISE_B, "peer2", approved=True)
    peer_id = "ab" * 8
    monkeypatch.setitem(pbs._PEER_NOISE_KEYS, peer_id, bytes.fromhex(NOISE_A))
    assert pbs._chat_room_descriptor({"via": "ble", "peer": peer_id}) == {
        "store": "bitchat",
        "peer_key": NOISE_A,
    }
    monkeypatch.setitem(pbs._PEER_NOISE_KEYS, peer_id, bytes.fromhex(NOISE_B))
    assert pbs._chat_room_descriptor({"via": "ble", "peer": peer_id}) is None

    # A peer paired only in the Nostr remote registry resolves there.
    def _pubkey(value: int) -> str:
        public_key = ec.derive_private_key(value, ec.SECP256K1()).public_key()
        return public_key.public_numbers().x.to_bytes(32, "big").hex()

    from uagent.nostr_remote_pairing import SQLitePairingStore

    nostr_db = tmp_path / "nostr-pairings.sqlite3"
    with SQLitePairingStore(nostr_db) as nstore:
        nstore.pair(_pubkey(61), "phone", approved=True, binding="room")
    monkeypatch.setattr(
        "uagent.tools.nostr_transport._pairing_database_path", lambda: nostr_db
    )
    assert pbs._chat_room_descriptor({"via": "nostr", "peer": _pubkey(61)}) == {
        "store": "nostr",
        "peer_key": _pubkey(61),
    }
    assert pbs._chat_room_descriptor(None) is None


def test_record_for_nostr_skips_revoked_pairings(store) -> None:
    # A peer that re-pairs under a new Noise identity keeps its Nostr
    # key: the revoked row must not shadow the active room binding.
    store.pair(NOISE_A, "old phone", approved=True)
    store.link_nostr(NOISE_A, NOSTR_A, approved=True)
    store.revoke(NOISE_A)
    store.pair(NOISE_B, "new phone", approved=True, binding="room")
    store.link_nostr(NOISE_B, NOSTR_A, approved=True)

    record = store.record_for_nostr(NOSTR_A)
    assert record is not None
    assert record.noise_key == NOISE_B
    assert record.binding == "room"
    assert record.active


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
    monkeypatch.setattr(pbs, "_RUNNING", True)
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


# ---- :bitchat pair by number / nickname (displayed peers only) ------------

_PEER_ID_A = bytes.fromhex("0102030405060708")
_PEER_ID_B = bytes.fromhex("1112131415161718")
_PEER_ID_C = bytes.fromhex("2122232425262728")


@pytest.fixture()
def cmd_env(tmp_path, monkeypatch):
    """Command handlers wired to a throwaway pairing registry."""
    from uagent import bitchat_pairing
    from uagent.tools import pybitchat_shared as pbs
    from uagent.tools import pybitchat_subscribe_tool as pst

    db = tmp_path / "cmd_pairings.sqlite3"
    monkeypatch.setattr(
        bitchat_pairing,
        "open_bitchat_pairing_store",
        lambda: SQLiteBitchatPairingStore(db),
    )
    monkeypatch.setattr(pbs, "_PEER_NICKNAMES", {})
    monkeypatch.setattr(pbs, "_PEER_NOISE_KEYS", {})
    monkeypatch.setattr(pst, "_DISPLAYED_BLE_PEERS", [])
    return pst, pbs, db


def _show_peers(pbs, pst, peers) -> None:
    """Make :bitchat peers display the given (peer_id, nick, key) rows."""
    pbs._PEER_NICKNAMES.clear()
    pbs._PEER_NOISE_KEYS.clear()
    for peer_id, nick, key_hex in peers:
        pbs._PEER_NICKNAMES[peer_id] = nick
        if key_hex is not None:
            pbs._PEER_NOISE_KEYS[peer_id] = bytes.fromhex(key_hex)
    pst._cmd_bitchat_peers("")


def _authorized(db, noise_key: str) -> bool:
    with SQLiteBitchatPairingStore(db) as s:
        return s.is_authorized_noise(noise_key)


def _label(db, noise_key: str) -> str:
    with SQLiteBitchatPairingStore(db) as s:
        record = s.record_for(noise_key)
    assert record is not None
    return record.label


def test_peers_numbers_ble_peers(cmd_env, capsys) -> None:
    pst, pbs, _db = cmd_env
    _show_peers(
        pbs,
        pst,
        [(_PEER_ID_A, "alice", NOISE_A), (_PEER_ID_B, "bob", NOISE_B)],
    )
    out = capsys.readouterr().out
    assert "1. alice" in out
    assert "2. bob" in out
    assert pst._DISPLAYED_BLE_PEERS == [("alice", NOISE_A), ("bob", NOISE_B)]


def test_pair_by_number(cmd_env) -> None:
    pst, pbs, db = cmd_env
    _show_peers(
        pbs,
        pst,
        [(_PEER_ID_A, "alice", NOISE_A), (_PEER_ID_B, "bob", NOISE_B)],
    )
    pst._cmd_bitchat_pair("2")
    assert not _authorized(db, NOISE_A)
    assert _authorized(db, NOISE_B)
    # With no explicit label the displayed nickname becomes the label.
    assert _label(db, NOISE_B) == "bob"


def test_pair_by_nickname(cmd_env) -> None:
    pst, pbs, db = cmd_env
    _show_peers(pbs, pst, [(_PEER_ID_A, "alice", NOISE_A)])
    pst._cmd_bitchat_pair("alice")
    assert _authorized(db, NOISE_A)
    assert _label(db, NOISE_A) == "alice"


def test_pair_by_nickname_with_label(cmd_env) -> None:
    pst, pbs, db = cmd_env
    _show_peers(pbs, pst, [(_PEER_ID_A, "alice", NOISE_A)])
    pst._cmd_bitchat_pair("alice phone")
    assert _authorized(db, NOISE_A)
    assert _label(db, NOISE_A) == "phone"


def test_pair_by_nickname_with_spaces(cmd_env) -> None:
    pst, pbs, db = cmd_env
    _show_peers(pbs, pst, [(_PEER_ID_A, "al ice", NOISE_A)])
    pst._cmd_bitchat_pair("al ice work")
    assert _authorized(db, NOISE_A)
    assert _label(db, NOISE_A) == "work"


def test_pair_unknown_selector_pairs_nothing(cmd_env, capsys) -> None:
    pst, pbs, db = cmd_env
    _show_peers(pbs, pst, [(_PEER_ID_A, "alice", NOISE_A)])
    pst._cmd_bitchat_pair("mallory")
    pst._cmd_bitchat_pair("9")
    out = capsys.readouterr().out
    assert "mallory" in out
    assert not _authorized(db, NOISE_A)


def test_pair_before_any_peers_display(cmd_env, capsys) -> None:
    pst, _pbs, db = cmd_env
    pst._cmd_bitchat_pair("alice")
    out = capsys.readouterr().out
    assert ":bitchat peers" in out
    assert not _authorized(db, NOISE_A)


def test_pair_ambiguous_nickname_pairs_nothing(cmd_env, capsys) -> None:
    pst, pbs, db = cmd_env
    _show_peers(
        pbs,
        pst,
        [(_PEER_ID_A, "bob", NOISE_A), (_PEER_ID_B, "bob", NOISE_B)],
    )
    pst._cmd_bitchat_pair("bob")
    out = capsys.readouterr().out
    assert "bob" in out
    assert not _authorized(db, NOISE_A)
    assert not _authorized(db, NOISE_B)
    # The number still disambiguates.
    pst._cmd_bitchat_pair("2")
    assert _authorized(db, NOISE_B)


def test_pair_by_full_key_without_display(cmd_env) -> None:
    pst, _pbs, db = cmd_env
    pst._cmd_bitchat_pair(f"{NOISE_A} phone")
    assert _authorized(db, NOISE_A)
    assert _label(db, NOISE_A) == "phone"


def test_displayed_list_is_refreshed_by_next_peers(cmd_env) -> None:
    pst, pbs, db = cmd_env
    _show_peers(pbs, pst, [(_PEER_ID_A, "alice", NOISE_A)])
    _show_peers(pbs, pst, [(_PEER_ID_C, "carol", NOISE_B)])
    # "alice" was displayed once but is not in the latest list anymore.
    pst._cmd_bitchat_pair("alice")
    assert not _authorized(db, NOISE_A)
    pst._cmd_bitchat_pair("1")
    assert _authorized(db, NOISE_B)


# ---- pairing authorizes the LLM in every chat mode ---------------------------


@pytest.fixture()
def any_mode(monkeypatch):
    """A running node in chat mode 'off' with a dummy LLM event queue."""
    from uagent.tools import pybitchat_shared as pbs

    events: queue.Queue = queue.Queue()
    monkeypatch.setattr(pbs, "_RUNNING", True)
    monkeypatch.setattr(pbs, "_CHAT_MODE", "off")
    pbs.set_llm_event_queue(events)
    yield pbs, events
    pbs.set_llm_event_queue(None)


def test_nostr_dm_injected_in_off_mode_when_paired(any_mode, monkeypatch) -> None:
    pbs, events = any_mode
    monkeypatch.setattr(pbs, "_is_paired_nostr_peer", lambda key: key == NOSTR_A)
    pbs._on_nostr_dm(NOSTR_A, "hello")
    event = events.get_nowait()
    assert event["reply_route"] == {"via": "nostr", "peer": NOSTR_A}


def test_nostr_dm_not_injected_when_node_stopped(any_mode, monkeypatch) -> None:
    pbs, events = any_mode
    monkeypatch.setattr(pbs, "_RUNNING", False)
    monkeypatch.setattr(pbs, "_is_paired_nostr_peer", lambda key: True)
    pbs._on_nostr_dm(NOSTR_A, "hello")
    assert events.empty()


def test_reply_sent_in_off_mode(any_mode, monkeypatch) -> None:
    pbs, _events = any_mode
    sent: list[tuple] = []
    monkeypatch.setattr(
        pbs,
        "enqueue_send",
        lambda type_, payload, recipient=None, via="ble", plain=False: sent.append(
            (type_, payload, recipient, via)
        ),
    )
    pbs.reply_to_bitchat_dm("answer", {"via": "ble", "peer": "0123456789abcdef"})
    assert sent == [("text", "answer", "0123456789abcdef", "ble")]


def test_forward_to_mesh_only_in_on_mode(any_mode, monkeypatch) -> None:
    pbs, _events = any_mode
    sent: list[tuple] = []
    monkeypatch.setattr(pbs, "_NOSTR_RUNNING", False)
    monkeypatch.setattr(
        pbs,
        "enqueue_send",
        lambda type_, payload, recipient=None, via="ble", plain=False: sent.append(
            (type_, payload, recipient, via)
        ),
    )
    for mode in ("off", "llm", "on"):
        monkeypatch.setattr(pbs, "_CHAT_MODE", mode)
        pbs.forward_to_mesh("local prompt")
    # Only the explicit public-chat mode forwards the local user's text.
    assert sent == [("text", "local prompt", None, "ble")]


def test_bind_command_switches_chat_binding(cmd_env, capsys) -> None:
    pst, _pbs, db = cmd_env
    pst._cmd_bitchat_pair(NOISE_A)
    pst._cmd_bitchat_bind(f"{NOISE_A} room")
    assert "room" in capsys.readouterr().out
    with SQLiteBitchatPairingStore(db) as s:
        record = s.record_for(NOISE_A)
        assert record is not None and record.binding == "room"
    pst._cmd_bitchat_devices("")
    assert "chat=room" in capsys.readouterr().out
    pst._cmd_bitchat_bind(f"{NOISE_A} attach")
    with SQLiteBitchatPairingStore(db) as s:
        record = s.record_for(NOISE_A)
        assert record is not None and record.binding == "attach"
    pst._cmd_bitchat_bind(NOISE_A)
    assert "Usage:" in capsys.readouterr().out
    pst._cmd_bitchat_bind(f"{NOISE_B} room")
    assert "No active pairing" in capsys.readouterr().out


def test_pair_command_does_not_change_chat_mode(cmd_env, any_mode) -> None:
    pst, pbs, _db = cmd_env
    pst._cmd_bitchat_pair(NOISE_A)
    assert pbs._CHAT_MODE == "off"

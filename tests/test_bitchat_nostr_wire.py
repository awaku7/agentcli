"""BitChat official wire format: envelope crypto, geohash events, filters."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from uagent.tools import _secp256k1 as secp
from uagent.tools import nostr_transport as nt


def _keypair() -> tuple[str, str]:
    priv = secp.generate_private_key()
    return priv.hex(), secp.private_to_public(priv).hex()


def _require_nacl() -> None:
    # pynacl is an optional runtime dependency (auto-installed on use);
    # the crypto envelope tests skip where it is not installed.
    pytest.importorskip("nacl")


def test_hkdf_sha256_matches_reference() -> None:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    ikm = bytes(range(32))
    # Empty salt in RFC 5869 means HashLen zero bytes.
    reference = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"\x00" * 32, info=b"nip44-v2"
    ).derive(ikm)
    assert nt._hkdf_sha256(ikm, b"", b"nip44-v2", 32) == reference

    reference2 = HKDF(
        algorithm=hashes.SHA256(), length=42, salt=b"salt", info=b"info"
    ).derive(ikm)
    assert nt._hkdf_sha256(ikm, b"salt", b"info", 42) == reference2


def test_bitchat_conversation_key_symmetric_and_distinct() -> None:
    from uagent.nostr_nip44 import nip44_v2_conversation_key

    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()

    key_ab = nt._bitchat_conversation_key(a_priv, b_pub)
    key_ba = nt._bitchat_conversation_key(b_priv, a_pub)
    assert key_ab == key_ba
    assert len(key_ab) == 32

    # Not the legacy raw-ECDH key and not the NIP-44 conversation key.
    legacy = secp.ecdh_shared_key(bytes.fromhex(a_priv), bytes.fromhex(b_pub))
    assert key_ab != legacy
    nip44 = nip44_v2_conversation_key(bytes.fromhex(a_priv), bytes.fromhex(b_pub))
    assert key_ab != nip44


def test_bitchat_encrypt_uses_base64url() -> None:
    _require_nacl()
    key = bytes(range(32))
    encoded = nt._bitchat_encrypt(b"hello bitchat", key)
    assert encoded.startswith("v2:")
    body = encoded[3:]
    assert "+" not in body and "/" not in body
    assert nt._bitchat_decrypt(encoded, key) == b"hello bitchat"
    assert nt._bitchat_decrypt(encoded, bytes(range(32, 64))) is None


def test_bitchat_dm_round_trip() -> None:
    _require_nacl()
    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()
    _, c_pub = _keypair()
    c_priv, _ = _keypair()

    wrap = nt._make_bitchat_dm_event("secret hello", a_priv, a_pub, b_pub)
    assert wrap["kind"] == 1059
    assert wrap["tags"] == [["p", b_pub]]
    # Signed by a one-time ephemeral key, not by the sender.
    assert wrap["pubkey"] != a_pub
    assert nt._verify_event(wrap)

    opened = nt._open_bitchat_dm_event(wrap, b_priv, b_pub)
    assert opened == (a_pub, "secret hello")

    # A third party cannot open it.
    assert nt._open_bitchat_dm_event(wrap, c_priv, c_pub) is None

    # Tampered content does not open.
    tampered = dict(wrap)
    body = wrap["content"]
    tampered["content"] = body[:10] + ("A" if body[10] != "A" else "B") + body[11:]
    assert nt._open_bitchat_dm_event(tampered, b_priv, b_pub) is None


def test_bitchat_dm_rejects_sender_mismatch() -> None:
    _require_nacl()
    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()
    x_priv, x_pub = _keypair()

    # Seal signed by X but the rumor claims to be from A.
    now = int(time.time())
    rumor = {
        "pubkey": a_pub,
        "created_at": now,
        "kind": 14,
        "tags": [["p", b_pub]],
        "content": "forged",
    }
    rumor["id"] = nt._compute_event_id(rumor)
    seal = {
        "pubkey": x_pub,
        "created_at": now,
        "kind": 13,
        "tags": [],
        "content": nt._bitchat_encrypt(
            json.dumps(rumor).encode("utf-8"),
            nt._bitchat_conversation_key(x_priv, b_pub),
        ),
    }
    seal["sig"] = nt._sign_event(seal, x_priv)
    eph_priv = secp.generate_private_key()
    wrap = {
        "pubkey": secp.private_to_public(eph_priv).hex(),
        "created_at": now,
        "kind": 1059,
        "tags": [["p", b_pub]],
        "content": nt._bitchat_encrypt(
            json.dumps(seal).encode("utf-8"),
            nt._bitchat_conversation_key(eph_priv.hex(), b_pub),
        ),
    }
    wrap["sig"] = nt._sign_event(wrap, eph_priv.hex())

    assert nt._open_bitchat_dm_event(wrap, b_priv, b_pub) is None


def test_legacy_dm_still_decrypts_via_fallback() -> None:
    _require_nacl()
    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()

    legacy = nt._make_kind1059_event("old format", a_priv, a_pub, b_pub)
    # The official opener must reject the legacy single-layer format...
    assert nt._open_bitchat_dm_event(legacy, b_priv, b_pub) is None
    # ...while the legacy decryptor still reads it.
    assert nt._decrypt_kind1059(legacy, b_priv, b_pub) == "old format"


def test_geo_event_shape() -> None:
    priv, pub = _keypair()
    event = nt._make_geo_event(20000, "hi all", "u4pruydq", "nick", priv, pub)
    assert event["kind"] == 20000
    assert event["tags"] == [["g", "u4pruydq"], ["n", "nick"]]
    assert event["content"] == "hi all"
    assert nt._verify_event(event)


def test_default_relays_are_official_set_plus_kojira() -> None:
    transport = nt.NostrTransport()
    assert set(transport.relays) == {
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.primal.net",
        "wss://offchain.pub",
        "wss://x.kojira.io",
    }


def test_subscription_requests() -> None:
    priv, pub = _keypair()
    transport = nt.NostrTransport(
        relays=["wss://example.invalid"], priv_hex=priv, pub_hex=pub
    )
    requests = dict(transport._subscription_requests())
    assert set(requests) == {"bitchat-dm", "bitchat-public"}
    dm_filter = requests["bitchat-dm"]
    assert dm_filter["kinds"] == [1059]
    assert dm_filter["#p"] == [pub]
    assert abs(dm_filter["since"] - (int(time.time()) - 86400)) <= 5

    transport.add_geo_filter("u4pruydq")
    requests = dict(transport._subscription_requests())
    geo_filter = requests["bitchat-geo"]
    assert geo_filter["kinds"] == [20000, 20001]
    assert geo_filter["#g"] == ["u4pruydq"]


def test_handle_event_official_dm_and_geohash() -> None:
    _require_nacl()
    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()

    received: list[tuple[str, str, str]] = []
    geo_messages: list[tuple[str, str, int]] = []
    transport = nt.NostrTransport(
        relays=["wss://example.invalid"],
        priv_hex=b_priv,
        pub_hex=b_pub,
        nickname="bob",
        on_message=lambda nick, text, kind: geo_messages.append((nick, text, kind)),
        on_kind1059=lambda sender, text, raw: received.append((sender, text, raw)),
    )

    wrap = nt._make_bitchat_dm_event("dm for bob", a_priv, a_pub, b_pub)
    asyncio.run(transport._handle_event(wrap))
    assert [(s, t) for s, t, _ in received] == [(a_pub, "dm for bob")]

    geo = nt._make_geo_event(20000, "geo hi", "u4pruydq", "alice", a_priv, a_pub)
    asyncio.run(transport._handle_event(geo))
    assert geo_messages == [("alice", "geo hi", 20000)]

    presence = nt._make_geo_event(20001, "", "u4pruydq", "alice", a_priv, a_pub)
    asyncio.run(transport._handle_event(presence))
    # Presence only updates the participant table; it is not a message.
    assert geo_messages == [("alice", "geo hi", 20000)]
    assert transport.discovered_peers[a_pub] == "alice"

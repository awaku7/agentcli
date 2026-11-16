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

    # Not the pre-fix schedule either (HKDF over the bare X coordinate):
    # upstream feeds the 33-byte compressed shared point into HKDF.
    x_only = nt._hkdf_sha256(legacy_x(a_priv, b_pub), b"", b"nip44-v2", 32)
    assert key_ab != x_only


def legacy_x(priv_hex: str, pub_hex: str) -> bytes:
    """Raw ECDH X via the reference library, lifting the peer key even-Y."""
    from cryptography.hazmat.primitives.asymmetric import ec

    p = (1 << 256) - (1 << 32) - 977  # secp256k1 field prime
    x = int(pub_hex, 16)
    y = pow((pow(x, 3, p) + 7) % p, (p + 1) // 4, p)
    if y % 2 != 0:
        y = p - y
    priv = ec.derive_private_key(int(priv_hex, 16), ec.SECP256K1())
    peer = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key()
    return priv.exchange(ec.ECDH(), peer)


def test_ecdh_shared_point_matches_reference_ecdh() -> None:
    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()

    point = nt._ecdh_shared_point(
        bytes.fromhex(a_priv), bytes.fromhex(b_pub), even=True
    )
    assert len(point) == 33
    assert point[0] in (2, 3)
    # The X part must equal the reference library's ECDH output.
    assert point[1:] == legacy_x(a_priv, b_pub)
    # The odd lift negates the shared point: same X, flipped parity byte.
    odd = nt._ecdh_shared_point(bytes.fromhex(a_priv), bytes.fromhex(b_pub), even=False)
    assert odd[1:] == point[1:]
    assert odd[0] != point[0]


def test_bitchat_encrypt_uses_base64url_without_padding() -> None:
    _require_nacl()
    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()
    key = nt._bitchat_conversation_key(a_priv, b_pub)
    encoded = nt._bitchat_encrypt(b"hello bitchat", key)
    assert encoded.startswith("v2:")
    body = encoded[3:]
    assert "+" not in body and "/" not in body and "=" not in body
    assert nt._bitchat_decrypt_any(encoded, b_priv, a_pub) == b"hello bitchat"
    _, c_pub = _keypair()
    assert nt._bitchat_decrypt_any(encoded, b_priv, c_pub) is None


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


def _make_dm_with_lift(
    content: str, a_priv: str, a_pub: str, b_pub: str, *, even: bool
) -> dict:
    """Build a DM envelope deriving both layers with the given Y lift."""
    now = int(time.time())
    rumor = {
        "pubkey": a_pub,
        "created_at": now,
        "kind": 14,
        "tags": [["p", b_pub]],
        "content": content,
    }
    rumor["id"] = nt._compute_event_id(rumor)
    seal = {
        "pubkey": a_pub,
        "created_at": now,
        "kind": 13,
        "tags": [],
        "content": nt._bitchat_encrypt(
            json.dumps(rumor).encode("utf-8"),
            nt._bitchat_conversation_key(a_priv, b_pub, even=even),
        ),
    }
    seal["sig"] = nt._sign_event(seal, a_priv)
    eph_priv = secp.generate_private_key()
    wrap = {
        "pubkey": secp.private_to_public(eph_priv).hex(),
        "created_at": now,
        "kind": 1059,
        "tags": [["p", b_pub]],
        "content": nt._bitchat_encrypt(
            json.dumps(seal).encode("utf-8"),
            nt._bitchat_conversation_key(eph_priv.hex(), b_pub, even=even),
        ),
    }
    wrap["sig"] = nt._sign_event(wrap, eph_priv.hex())
    return wrap


def test_bitchat_dm_odd_lift_still_opens() -> None:
    _require_nacl()
    a_priv, a_pub = _keypair()
    b_priv, b_pub = _keypair()

    # A sender that derived its keys with the odd-Y lift of our key must
    # still be readable: upstream receivers try even Y, then odd Y.
    wrap = _make_dm_with_lift("odd hello", a_priv, a_pub, b_pub, even=False)
    assert nt._open_bitchat_dm_event(wrap, b_priv, b_pub) == (a_pub, "odd hello")


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

    # Presence events must not carry the nickname tag (upstream spec).
    presence = nt._make_geo_event(20001, "", "u4pruyd", "nick", priv, pub)
    assert presence["tags"] == [["g", "u4pruyd"]]
    assert nt._verify_event(presence)


def test_presence_only_at_precision_5_or_below() -> None:
    priv, pub = _keypair()
    transport = nt.NostrTransport(
        relays=["wss://example.invalid"], priv_hex=priv, pub_hex=pub
    )
    transport.send_presence("u4pru")  # precision 5 (city): allowed
    assert transport._outbound.qsize() == 1
    transport.send_presence("u4pruy")  # precision 6 (neighborhood): suppressed
    transport.send_presence("u4pruydq")  # precision 8 (building): suppressed
    assert transport._outbound.qsize() == 1


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


def test_subscribe_loop_reacts_promptly_to_join() -> None:
    priv, pub = _keypair()
    transport = nt.NostrTransport(
        relays=["wss://example.invalid"], priv_hex=priv, pub_hex=pub
    )
    sent: list[str] = []

    class FakeWS:
        async def send(self, msg: str) -> None:
            sent.append(msg)

    transport._relay_connections["wss://example.invalid"] = FakeWS()

    async def run() -> None:
        task = asyncio.create_task(transport._subscribe_loop())
        try:
            transport.add_geo_filter("u4pruydq")
            for _ in range(30):
                await asyncio.sleep(0.1)
                if sent:
                    break
        finally:
            transport._stop_event.set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(run())
    assert sent, "geo subscription was not refreshed promptly after join"
    assert '"bitchat-geo"' in sent[0]
    assert "u4pruydq" in sent[0]


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

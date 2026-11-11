"""NIP-17/NIP-59 composition tests for the experimental remote-CLI path."""

from __future__ import annotations

import copy

import pytest

from uagent.nostr_nip17 import (
    _make_gift_wrap,
    _make_rumor,
    _make_seal,
    _public_key_x,
    create_nip17_private_messages,
    create_nip17_relay_list_event,
    extract_nip17_relay_list,
    unwrap_nip17_private_message,
)
from uagent.tools.nostr_transport import _verify_event


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


def test_nip17_round_trip_creates_recipient_and_sender_copies() -> None:
    sender_private = _secret(1)
    recipient_private = _secret(2)
    recipient_public = bytes.fromhex(
        "c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
    )
    text = "NIP-17 Python round trip / 日本語 🔐"

    gift_wraps = create_nip17_private_messages(
        text, sender_private, recipient_public, now=1_700_000_000
    )

    assert len(gift_wraps) == 2
    assert all(event["kind"] == 1059 and _verify_event(event) for event in gift_wraps)
    assert [event["tags"][0][1] for event in gift_wraps] == [
        recipient_public.hex(),
        "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
    ]

    received = unwrap_nip17_private_message(gift_wraps[0], recipient_private)
    sender_copy = unwrap_nip17_private_message(gift_wraps[1], sender_private)
    assert received["kind"] == 14
    assert received["content"] == text
    assert received["pubkey"] == sender_copy["pubkey"]
    assert received["id"] == sender_copy["id"]


def test_nip17_rejects_tampered_wrap_wrong_recipient_and_unsigned_wrap() -> None:
    sender_private = _secret(1)
    recipient_private = _secret(2)
    wrong_private = _secret(3)
    recipient_public = bytes.fromhex(
        "c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
    )
    gift = create_nip17_private_messages("message", sender_private, recipient_public)[0]

    with pytest.raises(ValueError):
        unwrap_nip17_private_message(gift, wrong_private)

    tampered = copy.deepcopy(gift)
    tampered["content"] = tampered["content"][:-1] + (
        "A" if tampered["content"][-1] != "A" else "B"
    )
    with pytest.raises(ValueError):
        unwrap_nip17_private_message(tampered, recipient_private)

    unsigned = copy.deepcopy(gift)
    unsigned.pop("sig")
    with pytest.raises(ValueError):
        unwrap_nip17_private_message(unsigned, recipient_private)


def test_nip17_rejects_invalid_rumor_addressing_and_invalid_key() -> None:
    with pytest.raises(ValueError):
        create_nip17_private_messages("message", bytes(32), bytes.fromhex("01" * 32))

    with pytest.raises(ValueError):
        create_nip17_private_messages("message", _secret(1), bytes.fromhex("ff" * 32))


def test_kind_10050_relay_list_round_trip_and_deduplication() -> None:
    private_key = _secret(1)
    public_key_hex = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    relays = ["wss://relay.example.org", "wss://relay2.example.org"]

    event = create_nip17_relay_list_event(
        [relays[0], relays[1], relays[0]], private_key, now=1_700_000_000
    )

    assert event["kind"] == 10050
    assert event["content"] == ""
    assert _verify_event(event)
    assert extract_nip17_relay_list(event, public_key_hex) == relays


def test_kind_10050_rejects_wrong_author_and_modified_event() -> None:
    private_key = _secret(1)
    other_public_key_hex = (
        "c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
    )
    event = create_nip17_relay_list_event(
        ["wss://relay.example.org"], private_key, now=1_700_000_000
    )

    with pytest.raises(ValueError):
        extract_nip17_relay_list(event, other_public_key_hex)

    tampered = copy.deepcopy(event)
    tampered["tags"].append(["relay", "wss://attacker.example"])
    with pytest.raises(ValueError):
        extract_nip17_relay_list(tampered, event["pubkey"])


def test_kind_10050_rejects_unsafe_or_malformed_relay_urls() -> None:
    private_key = _secret(1)
    invalid_relays = [
        "ws://relay.example.org",
        "https://relay.example.org",
        "wss://user:password@relay.example.org",
        "wss://relay.example.org/#fragment",
        "wss://relay.example.org:70000",
        "wss://relay.example.org/path with spaces",
    ]
    for relay in invalid_relays:
        with pytest.raises(ValueError):
            create_nip17_relay_list_event([relay], private_key, now=1_700_000_000)

    with pytest.raises(ValueError):
        create_nip17_relay_list_event([], private_key, now=1_700_000_000)


@pytest.mark.parametrize(
    ("signature", "accepted"),
    [
        ("", True),
        ("0" * 128, False),
        (None, False),
        (0, False),
    ],
)
def test_nip17_accepts_only_empty_serialized_rumor_signature(
    signature: object, accepted: bool
) -> None:
    # 0xChat's NIP-17 encoder sets sig="" before serializing the
    # otherwise unsigned rumor. Its event JSON always includes "sig".
    sender_private = _secret(1)
    recipient_private = _secret(2)
    sender_public = _public_key_x(sender_private)
    recipient_public = _public_key_x(recipient_private)
    timestamp = 1_700_000_000

    rumor = _make_rumor(
        sender_public_key=sender_public,
        recipient_public_key=recipient_public,
        text="/uag status",
        created_at=timestamp,
    )
    rumor["sig"] = signature
    seal = _make_seal(
        rumor=rumor,
        sender_private_key=sender_private,
        sender_public_key=sender_public,
        receiver_public_key=recipient_public,
        now=timestamp,
    )
    wrap = _make_gift_wrap(
        seal=seal, receiver_public_key=recipient_public, now=timestamp
    )

    if accepted:
        received = unwrap_nip17_private_message(wrap, recipient_private)
        assert received["content"] == "/uag status"
        assert received["sig"] == ""
        assert received["pubkey"] == sender_public.hex()
    else:
        with pytest.raises(ValueError, match="rumor must be unsigned"):
            unwrap_nip17_private_message(wrap, recipient_private)

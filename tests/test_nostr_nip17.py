"""NIP-17/NIP-59 composition tests for the experimental remote-CLI path."""

from __future__ import annotations

import copy

import pytest

from uagent.nostr_nip17 import (
    create_nip17_private_messages,
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

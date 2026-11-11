"""Independent NIP-17 interoperability checks against the Rust-backed nostr-sdk.

The SDK is a test-only dependency. No relay or real credentials are needed.
"""

from __future__ import annotations

import json

import pytest

from uagent.nostr_nip17 import (
    _public_key_x,
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)

nostr_sdk = pytest.importorskip("nostr_sdk")


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


@pytest.mark.parametrize("text", ["hello from UAG", "日本語の返信 🔐 NIP-17"])
def test_uag_recipient_and_sender_wraps_unwrap_with_nostr_sdk(text: str) -> None:
    sender_private = _secret(1)
    recipient_private = _secret(2)
    sender_public = _public_key_x(sender_private)
    recipient_public = _public_key_x(recipient_private)
    wraps = create_nip17_private_messages(
        text, sender_private, recipient_public, now=1_700_000_000
    )

    assert len(wraps) == 2
    for wrap, private_key in zip(
        wraps, (recipient_private, sender_private), strict=True
    ):
        sdk_event = nostr_sdk.Event.from_json(json.dumps(wrap, ensure_ascii=False))
        decoded = nostr_sdk.UnwrappedGift.from_gift_wrap(
            nostr_sdk.Keys.parse(private_key.hex()), sdk_event
        )
        rumor = json.loads(decoded.rumor().as_json())
        assert decoded.sender().to_hex() == sender_public.hex()
        assert rumor["kind"] == 14
        assert rumor["pubkey"] == sender_public.hex()
        assert rumor["tags"] == [["p", recipient_public.hex()]]
        assert rumor["content"] == text


@pytest.mark.parametrize("text", ["hello from nostr-sdk", "日本語のSDK返信 🔐 NIP-17"])
def test_nostr_sdk_gift_wrap_unwraps_with_uag(text: str) -> None:
    sender_private = _secret(3)
    recipient_private = _secret(4)
    sender_public = _public_key_x(sender_private)
    recipient_public = _public_key_x(recipient_private)

    sdk_event = nostr_sdk.nip17_make_private_msg(
        nostr_sdk.Keys.parse(sender_private.hex()),
        nostr_sdk.PublicKey.parse(recipient_public.hex()),
        text,
    )
    gift_wrap = json.loads(sdk_event.as_json())
    rumor = unwrap_nip17_private_message(gift_wrap, recipient_private)

    assert gift_wrap["kind"] == 1059
    assert rumor["kind"] == 14
    assert rumor["pubkey"] == sender_public.hex()
    assert rumor["tags"] == [["p", recipient_public.hex()]]
    assert rumor["content"] == text

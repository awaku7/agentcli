"""Generate public test-key NIP-17 wraps for 0xChat's Dart decoder.

The private keys here are deterministic TEST KEYS and must never be used for
real accounts. No private data from a user's 0xChat account is required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from uagent.nostr_nip17 import (
    _public_key_x,
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)

_TEST_SENDER_PRIVATE = (1).to_bytes(32, "big")
_TEST_RECIPIENT_PRIVATE = (2).to_bytes(32, "big")
_TEST_TIMESTAMP = 1_700_000_000


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: build_0xchat_fixture.py OUTPUT.json")
    sender_public = _public_key_x(_TEST_SENDER_PRIVATE)
    recipient_public = _public_key_x(_TEST_RECIPIENT_PRIVATE)
    cases = []
    for name, content in (
        ("short", "Hello from UAG → 0xChat / 日本語 🔐"),
        ("long", "UAG reply / 日本語 / " * 650),
    ):
        wraps = create_nip17_private_messages(
            content,
            _TEST_SENDER_PRIVATE,
            recipient_public,
            now=_TEST_TIMESTAMP,
        )
        assert len(wraps) == 2
        rumor = unwrap_nip17_private_message(wraps[0], _TEST_RECIPIENT_PRIVATE)
        assert rumor["content"] == content
        assert unwrap_nip17_private_message(wraps[1], _TEST_SENDER_PRIVATE)[
            "id"
        ] == rumor["id"]
        cases.append(
            {
                "name": name,
                "content": content,
                "sender_private_key": _TEST_SENDER_PRIVATE.hex(),
                "sender_public_key": sender_public.hex(),
                "recipient_private_key": _TEST_RECIPIENT_PRIVATE.hex(),
                "recipient_public_key": recipient_public.hex(),
                "recipient_wrap": wraps[0],
                "sender_wrap": wraps[1],
            }
        )

    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cases": cases}, ensure_ascii=False), encoding="utf-8")
    print(f"Generated {len(cases)} NIP-17 fixtures with TEST KEYS")


if __name__ == "__main__":
    main()

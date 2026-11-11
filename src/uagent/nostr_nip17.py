"""Experimental NIP-17/NIP-59 text-DM composition for remote-CLI evaluation.

This module is not wired into the Nostr transport or CLI dispatcher. It composes
NIP-17 kind-14 rumors, NIP-59 seals/gift wraps, and the isolated Python NIP-44
implementation. Keep it experimental until independent interoperability and
security review pass.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any
from urllib.parse import urlsplit

from .nostr_nip44 import nip44_v2_decrypt, nip44_v2_encrypt

_TWO_DAYS_SECONDS = 2 * 24 * 60 * 60
_SECP256K1_ORDER = int(
    "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16
)


def _load_ec() -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError as exc:
        raise ModuleNotFoundError(
            "NIP-17 key handling requires the 'cryptography' package"
        ) from exc
    return ec


def _validate_private_key(private_key: bytes) -> bytes:
    if not isinstance(private_key, (bytes, bytearray, memoryview)):
        raise TypeError("private_key must be bytes-like")
    value = bytes(private_key)
    if len(value) != 32:
        raise ValueError("private_key must be exactly 32 bytes")
    scalar = int.from_bytes(value, "big")
    if not 1 <= scalar < _SECP256K1_ORDER:
        raise ValueError("private_key is outside the secp256k1 scalar range")
    return value


def _public_key_x(private_key: bytes) -> bytes:
    ec = _load_ec()
    private = ec.derive_private_key(
        int.from_bytes(_validate_private_key(private_key), "big"), ec.SECP256K1()
    )
    return private.public_key().public_numbers().x.to_bytes(32, "big")


def _random_private_key() -> bytes:
    while True:
        candidate = secrets.token_bytes(32)
        if 1 <= int.from_bytes(candidate, "big") < _SECP256K1_ORDER:
            return candidate


def _event_id(event: dict[str, Any]) -> str:
    serialized = json.dumps(
        [
            0,
            event["pubkey"],
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"],
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _event_json(event: dict[str, Any]) -> str:
    return json.dumps(event, separators=(",", ":"), ensure_ascii=False)


def _sign_event(event: dict[str, Any], private_key: bytes) -> dict[str, Any]:
    # Reuse the repository's existing NIP-01 Schnorr event signer. The helper
    # sets `id` before returning the signature; it does not mutate other fields.
    from .tools.nostr_transport import _sign_event as sign_nip01_event

    signature = sign_nip01_event(event, private_key.hex())
    event["sig"] = signature
    return event


def _verify_event(event: dict[str, Any]) -> bool:
    from .tools.nostr_transport import _verify_event as verify_nip01_event

    return verify_nip01_event(event)


def _randomized_timestamp(now: int) -> int:
    return now - secrets.randbelow(_TWO_DAYS_SECONDS + 1)


def _make_rumor(
    *, sender_public_key: bytes, recipient_public_key: bytes, text: str, created_at: int
) -> dict[str, Any]:
    rumor: dict[str, Any] = {
        "pubkey": sender_public_key.hex(),
        "created_at": created_at,
        "kind": 14,
        "tags": [["p", recipient_public_key.hex()]],
        "content": text,
    }
    rumor["id"] = _event_id(rumor)
    return rumor


def _make_seal(
    *,
    rumor: dict[str, Any],
    sender_private_key: bytes,
    sender_public_key: bytes,
    receiver_public_key: bytes,
    now: int,
) -> dict[str, Any]:
    seal: dict[str, Any] = {
        "pubkey": sender_public_key.hex(),
        "created_at": _randomized_timestamp(now),
        "kind": 13,
        "tags": [],
        "content": nip44_v2_encrypt(
            _event_json(rumor), sender_private_key, receiver_public_key
        ),
    }
    return _sign_event(seal, sender_private_key)


def _make_gift_wrap(
    *, seal: dict[str, Any], receiver_public_key: bytes, now: int
) -> dict[str, Any]:
    ephemeral_private_key = _random_private_key()
    ephemeral_public_key = _public_key_x(ephemeral_private_key)
    gift_wrap: dict[str, Any] = {
        "pubkey": ephemeral_public_key.hex(),
        "created_at": _randomized_timestamp(now),
        "kind": 1059,
        "tags": [["p", receiver_public_key.hex()]],
        "content": nip44_v2_encrypt(
            _event_json(seal), ephemeral_private_key, receiver_public_key
        ),
    }
    return _sign_event(gift_wrap, ephemeral_private_key)


def create_nip17_private_messages(
    text: str,
    sender_private_key: bytes,
    recipient_public_key: bytes,
    *,
    now: int | None = None,
) -> list[dict[str, Any]]:
    """Create NIP-17 kind-1059 gift wraps for a one-to-one text DM.

    Returns one independently wrapped event for the recipient and one for the
    sender's own inbox, as required by the NIP-17 delivery convention. Each event
    uses a fresh ephemeral wrapper key. This helper does not publish to relays or
    decide which relays may receive the events.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    sender_private_key = _validate_private_key(sender_private_key)
    if not isinstance(recipient_public_key, (bytes, bytearray, memoryview)):
        raise TypeError("recipient_public_key must be bytes-like")
    recipient_public_key = bytes(recipient_public_key)
    if len(recipient_public_key) != 32:
        raise ValueError("recipient_public_key must be exactly 32 bytes")

    ec = _load_ec()
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), b"\x02" + recipient_public_key
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("recipient_public_key is not a valid x-only key") from exc

    sender_public_key = _public_key_x(sender_private_key)
    timestamp = int(time.time()) if now is None else int(now)
    rumor = _make_rumor(
        sender_public_key=sender_public_key,
        recipient_public_key=recipient_public_key,
        text=text,
        created_at=timestamp,
    )

    recipients = [recipient_public_key]
    if sender_public_key != recipient_public_key:
        recipients.append(sender_public_key)

    wraps: list[dict[str, Any]] = []
    for receiver in recipients:
        seal = _make_seal(
            rumor=rumor,
            sender_private_key=sender_private_key,
            sender_public_key=sender_public_key,
            receiver_public_key=receiver,
            now=timestamp,
        )
        wraps.append(
            _make_gift_wrap(seal=seal, receiver_public_key=receiver, now=timestamp)
        )
    return wraps


def _validate_relay_uri(uri: Any) -> str:
    """Validate NIP-17 inbox relay URI syntax, not destination trust."""
    if not isinstance(uri, str) or not uri or uri != uri.strip():
        raise ValueError("relay URI must be a non-empty trimmed string")
    if any(char.isspace() or ord(char) < 0x20 for char in uri):
        raise ValueError("relay URI contains whitespace or control characters")

    try:
        parsed = urlsplit(uri)
        # Accessing .port validates its numeric range and syntax.
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("relay URI is malformed") from exc

    if (
        parsed.scheme.lower() != "wss"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("relay URI must be a credential-free wss URL")
    return uri


def create_nip17_relay_list_event(
    relay_uris: list[str], private_key: bytes, *, now: int | None = None
) -> dict[str, Any]:
    """Create and sign a NIP-17 kind-10050 inbox relay list event."""
    if not isinstance(relay_uris, list):
        raise TypeError("relay_uris must be a list of URLs")
    if not relay_uris:
        raise ValueError("at least one inbox relay is required")

    private_key = _validate_private_key(private_key)
    public_key = _public_key_x(private_key)
    tags: list[list[str]] = []
    seen: set[str] = set()
    for uri in relay_uris:
        relay_uri = _validate_relay_uri(uri)
        if relay_uri not in seen:
            tags.append(["relay", relay_uri])
            seen.add(relay_uri)

    event: dict[str, Any] = {
        "pubkey": public_key.hex(),
        "created_at": int(time.time()) if now is None else int(now),
        "kind": 10050,
        "tags": tags,
        "content": "",
    }
    return _sign_event(event, private_key)


def extract_nip17_relay_list(
    event: dict[str, Any], expected_pubkey_hex: str
) -> list[str]:
    """Verify and extract a participant's signed kind-10050 relay list.

    The expected key must come from the authenticated DM participant, not from
    this event. Returned URLs are not trusted destinations by themselves;
    callers must apply local egress/relay policy before connecting.
    """
    if not isinstance(expected_pubkey_hex, str) or len(expected_pubkey_hex) != 64:
        raise ValueError("expected_pubkey_hex must be a 32-byte hex public key")
    try:
        expected_pubkey = bytes.fromhex(expected_pubkey_hex).hex()
    except ValueError as exc:
        raise ValueError("expected_pubkey_hex is malformed") from exc

    event = _validate_event_shape(event, kind=10050, name="relay-list event")
    if event["pubkey"] != expected_pubkey or not _verify_event(event):
        raise ValueError("relay-list event author or signature is invalid")
    if event["content"] != "":
        raise ValueError("NIP-17 relay-list event content must be empty")

    relay_uris: list[str] = []
    seen: set[str] = set()
    for tag in event["tags"]:
        if not isinstance(tag, list) or not tag or tag[0] != "relay":
            continue
        if len(tag) != 2:
            raise ValueError("NIP-17 relay tags must contain exactly one URI")
        uri = _validate_relay_uri(tag[1])
        if uri not in seen:
            relay_uris.append(uri)
            seen.add(uri)
    if not relay_uris:
        raise ValueError("relay-list event contains no valid inbox relays")
    return relay_uris


def _validate_event_shape(event: Any, *, kind: int, name: str) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError(f"{name} must be a JSON object")
    if event.get("kind") != kind:
        raise ValueError(f"{name} has the wrong event kind")
    if not isinstance(event.get("pubkey"), str) or len(event["pubkey"]) != 64:
        raise ValueError(f"{name} has an invalid pubkey")
    if not isinstance(event.get("content"), str):
        raise ValueError(f"{name} has invalid content")
    if not isinstance(event.get("tags"), list):
        raise ValueError(f"{name} has invalid tags")
    if not isinstance(event.get("created_at"), int) or isinstance(
        event.get("created_at"), bool
    ):
        raise ValueError(f"{name} has an invalid timestamp")
    return event


def unwrap_nip17_private_message(
    gift_wrap: dict[str, Any], receiver_private_key: bytes
) -> dict[str, Any]:
    """Verify and unwrap a one-to-one NIP-17 kind-14 text message.

    Relay-provided event size limits, expiry policy, authorization, and replay
    protection belong to the caller. The outer gift-wrap signature is verified
    before decryption; the seal signature and rumor identity are then checked.
    """
    receiver_private_key = _validate_private_key(receiver_private_key)
    receiver_public_key = _public_key_x(receiver_private_key)
    gift_wrap = _validate_event_shape(gift_wrap, kind=1059, name="gift wrap")
    if not _verify_event(gift_wrap):
        raise ValueError("invalid gift-wrap event signature")

    p_tags = [
        tag
        for tag in gift_wrap["tags"]
        if isinstance(tag, list) and len(tag) >= 2 and tag[0] == "p"
    ]
    if len(p_tags) != 1 or p_tags[0][1] != receiver_public_key.hex():
        raise ValueError("gift wrap is not addressed to this recipient")

    try:
        seal_json = nip44_v2_decrypt(
            gift_wrap["content"],
            receiver_private_key,
            bytes.fromhex(gift_wrap["pubkey"]),
        )
        seal = json.loads(seal_json)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("gift-wrap payload could not be opened") from exc

    seal = _validate_event_shape(seal, kind=13, name="seal")
    if seal["tags"] != []:
        raise ValueError("NIP-59 seal tags must be empty")
    if not _verify_event(seal):
        raise ValueError("invalid seal event signature")

    try:
        rumor_json = nip44_v2_decrypt(
            seal["content"], receiver_private_key, bytes.fromhex(seal["pubkey"])
        )
        rumor = json.loads(rumor_json)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("seal payload could not be opened") from exc

    rumor = _validate_event_shape(rumor, kind=14, name="rumor")
    # Some NIP-17 clients serialize unsigned rumors with an empty signature.
    # An empty string is not a signature; reject any non-empty or non-string value.
    if "sig" in rumor and rumor["sig"] != "":
        raise ValueError("NIP-17 rumor must be unsigned")
    if rumor["pubkey"] != seal["pubkey"]:
        raise ValueError("rumor author does not match authenticated seal author")
    if rumor.get("id") != _event_id(rumor):
        raise ValueError("rumor event id is invalid")
    rumor_p_tags = [
        tag
        for tag in rumor["tags"]
        if isinstance(tag, list) and len(tag) >= 2 and tag[0] == "p"
    ]
    is_sender_copy = rumor["pubkey"] == receiver_public_key.hex()
    is_recipient_copy = (
        len(rumor_p_tags) == 1 and rumor_p_tags[0][1] == receiver_public_key.hex()
    )
    if not (is_sender_copy or is_recipient_copy):
        raise ValueError("NIP-17 rumor is not addressed to this participant")
    return rumor

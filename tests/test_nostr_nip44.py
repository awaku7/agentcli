"""NIP-44 v2 conformance tests for the isolated remote-CLI implementation."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from uagent.nostr_nip44 import (
    _chacha20,
    _decrypt_with_conversation_key,
    _derive_message_keys,
    _encrypt_with_nonce,
    calc_padded_length,
    nip44_v2_conversation_key,
    nip44_v2_decrypt,
    nip44_v2_encrypt,
)

# Official NIP-44 v2 test vectors from https://github.com/paulmillr/nip44/blob/master/nip44.vectors.json
_VECTOR_PATH = Path(__file__).parent / "fixtures" / "nip44.vectors.json"
_VECTOR_SHA256 = "269ed0f69e4c192512cc779e78c555090cebc7c785b609e338a62afc3ce25040"


@pytest.fixture(scope="module")
def vectors() -> dict:
    raw = _VECTOR_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _VECTOR_SHA256
    return json.loads(raw)["v2"]


def _public_x(secret_hex: str) -> bytes:
    private = ec.derive_private_key(int(secret_hex, 16), ec.SECP256K1())
    return private.public_key().public_numbers().x.to_bytes(32, "big")


def test_official_conversation_key_vectors(vectors: dict) -> None:
    for vector in vectors["valid"]["get_conversation_key"]:
        actual = nip44_v2_conversation_key(
            bytes.fromhex(vector["sec1"]), bytes.fromhex(vector["pub2"])
        )
        assert actual.hex() == vector["conversation_key"]


def test_official_message_key_vectors(vectors: dict) -> None:
    data = vectors["valid"]["get_message_keys"]
    conversation_key = bytes.fromhex(data["conversation_key"])
    for vector in data["keys"]:
        actual = _derive_message_keys(conversation_key, bytes.fromhex(vector["nonce"]))
        assert actual[0].hex() == vector["chacha_key"]
        assert actual[1].hex() == vector["chacha_nonce"]
        assert actual[2].hex() == vector["hmac_key"]


def test_official_padding_length_vectors(vectors: dict) -> None:
    for plaintext_length, expected in vectors["valid"]["calc_padded_len"]:
        assert calc_padded_length(plaintext_length) == expected


@pytest.mark.parametrize(
    "length,expected_prefix_length",
    [(65_535, 2), (65_536, 6), (65_537, 6)],
)
def test_extended_length_prefix_boundaries(
    length: int, expected_prefix_length: int
) -> None:
    plaintext = b"a" * length
    nonce = bytes.fromhex("00" * 31 + "01")
    conversation_key = bytes.fromhex(
        "c41c775356fd92eadc63ff5a0dc1da211b268cbea22316767095b2871ea1412d"
    )
    payload = _encrypt_with_nonce(plaintext, conversation_key, nonce)
    decoded = base64.b64decode(payload, validate=True)
    ciphertext = decoded[33:-32]
    chacha_key, chacha_nonce, _ = _derive_message_keys(conversation_key, nonce)
    padded = _chacha20(chacha_key, chacha_nonce, ciphertext)
    assert padded[:2] == (length.to_bytes(2, "big") if length < 65_536 else b"\x00\x00")
    if expected_prefix_length == 6:
        assert int.from_bytes(padded[2:6], "big") == length
    assert _decrypt_with_conversation_key(payload, conversation_key) == plaintext


def test_official_fixed_nonce_encrypt_decrypt_vectors(vectors: dict) -> None:
    for vector in vectors["valid"]["encrypt_decrypt"]:
        secret1 = bytes.fromhex(vector["sec1"])
        secret2 = bytes.fromhex(vector["sec2"])
        nonce = bytes.fromhex(vector["nonce"])
        public1 = _public_x(vector["sec1"])
        public2 = _public_x(vector["sec2"])
        conversation_key = nip44_v2_conversation_key(secret1, public2)

        assert conversation_key.hex() == vector["conversation_key"]
        payload = _encrypt_with_nonce(
            vector["plaintext"].encode("utf-8"), conversation_key, nonce
        )
        assert payload == vector["payload"]
        assert nip44_v2_conversation_key(secret2, public1) == conversation_key
        assert _decrypt_with_conversation_key(
            payload, nip44_v2_conversation_key(secret2, public1)
        ) == vector["plaintext"].encode("utf-8")


def test_official_long_message_vectors(vectors: dict) -> None:
    for vector in vectors["valid"]["encrypt_decrypt_long_msg"]:
        plaintext = (vector["pattern"] * vector["repeat"]).encode("utf-8")
        assert hashlib.sha256(plaintext).hexdigest() == vector["plaintext_sha256"]
        payload = _encrypt_with_nonce(
            plaintext,
            bytes.fromhex(vector["conversation_key"]),
            bytes.fromhex(vector["nonce"]),
        )
        assert (
            hashlib.sha256(payload.encode("ascii")).hexdigest()
            == vector["payload_sha256"]
        )
        assert (
            _decrypt_with_conversation_key(
                payload, bytes.fromhex(vector["conversation_key"])
            )
            == plaintext
        )


def test_official_invalid_decrypt_vectors_are_rejected(vectors: dict) -> None:
    for vector in vectors["invalid"]["decrypt"]:
        with pytest.raises(ValueError):
            _decrypt_with_conversation_key(
                vector["payload"], bytes.fromhex(vector["conversation_key"])
            )


def test_invalid_conversation_key_vectors_are_rejected(vectors: dict) -> None:
    for vector in vectors["invalid"]["get_conversation_key"]:
        with pytest.raises(ValueError):
            nip44_v2_conversation_key(
                bytes.fromhex(vector["sec1"]), bytes.fromhex(vector["pub2"])
            )


def test_public_encrypt_decrypt_uses_fresh_nonce() -> None:
    secret1 = bytes.fromhex("00" * 31 + "01")
    secret2 = bytes.fromhex("00" * 31 + "02")
    public1 = _public_x(secret1.hex())
    public2 = _public_x(secret2.hex())
    plaintext = "NIP-44 v2 / 日本語 / 🔐"

    payload1 = nip44_v2_encrypt(plaintext, secret1, public2)
    payload2 = nip44_v2_encrypt(plaintext, secret1, public2)
    assert payload1 != payload2
    assert nip44_v2_decrypt(payload1, secret2, public1) == plaintext
    assert nip44_v2_decrypt(payload2, secret2, public1) == plaintext


def test_modified_payload_and_wrong_key_fail_authentication() -> None:
    secret1 = bytes.fromhex("00" * 31 + "01")
    secret2 = bytes.fromhex("00" * 31 + "02")
    secret3 = bytes.fromhex("00" * 31 + "03")
    public1 = _public_x(secret1.hex())
    public2 = _public_x(secret2.hex())
    payload = nip44_v2_encrypt("authenticated", secret1, public2)

    decoded = bytearray(base64.b64decode(payload, validate=True))
    decoded[-1] ^= 1
    tampered = base64.b64encode(decoded).decode("ascii")
    with pytest.raises(ValueError):
        nip44_v2_decrypt(tampered, secret2, public1)
    with pytest.raises(ValueError):
        nip44_v2_decrypt(payload, secret3, public1)


@pytest.mark.parametrize("plaintext", ["", "a\ud800b"])
def test_invalid_plaintext_is_rejected(plaintext: str) -> None:
    secret = bytes.fromhex("00" * 31 + "01")
    peer_public = _public_x((bytes.fromhex("00" * 31 + "02")).hex())
    with pytest.raises(ValueError):
        nip44_v2_encrypt(plaintext, secret, peer_public)


def test_malformed_payload_is_rejected() -> None:
    secret = bytes.fromhex("00" * 31 + "01")
    peer_public = _public_x((bytes.fromhex("00" * 31 + "02")).hex())
    for payload in ("", "not base64", "AQ=="):
        with pytest.raises(ValueError):
            nip44_v2_decrypt(payload, secret, peer_public)

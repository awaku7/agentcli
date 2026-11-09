"""Experimental Python NIP-44 v2 primitives for the remote-CLI design.

This module is deliberately not wired into a transport or command path yet. It
is an evaluation implementation: do not use it for remote control until the
complete NIP-44 vector suite, independent interoperability tests, and security
review pass.

The private-key ECDH and payload format follow NIP-44 v2. ECDH and ChaCha20 are
provided by ``cryptography``'s native backend; protocol framing, HKDF, HMAC,
and padding are implemented here so the extended-length vectors can be tested.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from typing import Any

__all__ = [
    "MAX_PLAINTEXT_SIZE",
    "calc_padded_length",
    "nip44_v2_conversation_key",
    "nip44_v2_decrypt",
    "nip44_v2_encrypt",
]

_NIP44_V2_SALT = b"nip44-v2"
_NONCE_SIZE = 32
_CHACHA_NONCE_SIZE = 12
_MAC_SIZE = 32
_VERSION = 2
_MAX_HKDF_OUTPUT = 255 * 32
_SECP256K1_ORDER = int(
    "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16
)
MAX_PLAINTEXT_SIZE = 0xFFFFFFFF


def _load_crypto() -> tuple[Any, Any, Any]:
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    except ImportError as exc:
        raise ModuleNotFoundError(
            "NIP-44 v2 requires the 'cryptography' package"
        ) from exc
    return ec, Cipher, algorithms


def _require_bytes(value: bytes | bytearray | memoryview, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{name} must be bytes-like")
    return bytes(value)


def _derive_shared_x(secret_key: bytes, public_key_x: bytes) -> bytes:
    secret_key = _require_bytes(secret_key, "secret_key")
    public_key_x = _require_bytes(public_key_x, "public_key_x")
    if len(secret_key) != 32:
        raise ValueError("secret_key must be exactly 32 bytes")
    if len(public_key_x) != 32:
        raise ValueError("public_key_x must be exactly 32 bytes")

    scalar = int.from_bytes(secret_key, "big")
    if not 1 <= scalar < _SECP256K1_ORDER:
        raise ValueError("secret_key is outside the secp256k1 scalar range")

    ec, _, _ = _load_crypto()
    try:
        private_key = ec.derive_private_key(scalar, ec.SECP256K1())
        # Nostr public keys are x-only and BIP-340 interprets them as the even-y
        # point. SEC1 prefix 0x02 selects that point when decompressing x.
        peer_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), b"\x02" + public_key_x
        )
        shared_x = private_key.exchange(ec.ECDH(), peer_key)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid secp256k1 key material") from exc

    if len(shared_x) != 32:
        raise ValueError("unexpected secp256k1 ECDH output length")
    return shared_x


def nip44_v2_conversation_key(secret_key: bytes, public_key_x: bytes) -> bytes:
    """Derive the 32-byte NIP-44 v2 conversation key.

    ``public_key_x`` is the other party's 32-byte x-only secp256k1 public key.
    The ECDH x-coordinate is used unhashed as the HKDF input key material, as
    required by NIP-44 v2.
    """
    shared_x = _derive_shared_x(secret_key, public_key_x)
    return hmac.new(_NIP44_V2_SALT, shared_x, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    if len(prk) != 32:
        raise ValueError("conversation key must be exactly 32 bytes")
    if not 0 <= length <= _MAX_HKDF_OUTPUT:
        raise ValueError("HKDF output length is invalid")

    output = bytearray()
    previous = b""
    counter = 1
    while len(output) < length:
        previous = hmac.new(
            prk, previous + info + bytes((counter,)), hashlib.sha256
        ).digest()
        output.extend(previous)
        counter += 1
    return bytes(output[:length])


def _derive_message_keys(
    conversation_key: bytes, nonce: bytes
) -> tuple[bytes, bytes, bytes]:
    conversation_key = _require_bytes(conversation_key, "conversation_key")
    nonce = _require_bytes(nonce, "nonce")
    if len(conversation_key) != 32:
        raise ValueError("conversation_key must be exactly 32 bytes")
    if len(nonce) != _NONCE_SIZE:
        raise ValueError("nonce must be exactly 32 bytes")

    material = _hkdf_expand(conversation_key, nonce, 76)
    return material[:32], material[32:44], material[44:76]


def calc_padded_length(plaintext_length: int) -> int:
    """Return the NIP-44 v2 padding bucket for a plaintext byte length."""
    if not isinstance(plaintext_length, int) or isinstance(plaintext_length, bool):
        raise TypeError("plaintext_length must be an integer")
    if not 1 <= plaintext_length <= MAX_PLAINTEXT_SIZE:
        raise ValueError("plaintext length is outside the NIP-44 v2 range")
    if plaintext_length <= 32:
        return 32

    next_power = 1 << (plaintext_length - 1).bit_length()
    chunk = 32 if next_power <= 256 else next_power // 8
    return ((plaintext_length - 1) // chunk + 1) * chunk


def _chacha20(key: bytes, nonce: bytes, data: bytes) -> bytes:
    if len(key) != 32 or len(nonce) != _CHACHA_NONCE_SIZE:
        raise ValueError("invalid NIP-44 ChaCha20 key or nonce length")
    _, Cipher, algorithms = _load_crypto()
    # cryptography's ChaCha20 API takes a 32-bit little-endian block counter
    # followed by the 96-bit IETF nonce used by NIP-44 v2.
    cipher = Cipher(algorithms.ChaCha20(key, b"\x00" * 4 + nonce), mode=None)
    context = cipher.encryptor()
    return context.update(data) + context.finalize()


def _encrypt_with_nonce(plaintext: bytes, conversation_key: bytes, nonce: bytes) -> str:
    """Deterministic internal helper used by official-vector tests only."""
    plaintext = _require_bytes(plaintext, "plaintext")
    if not 1 <= len(plaintext) <= MAX_PLAINTEXT_SIZE:
        raise ValueError("plaintext length is outside the NIP-44 v2 range")

    nonce = _require_bytes(nonce, "nonce")
    chacha_key, chacha_nonce, hmac_key = _derive_message_keys(conversation_key, nonce)
    padded_length = calc_padded_length(len(plaintext))
    if len(plaintext) < 65_536:
        length_prefix = len(plaintext).to_bytes(2, "big")
    else:
        length_prefix = b"\x00\x00" + len(plaintext).to_bytes(4, "big")
    padded = length_prefix + plaintext + b"\x00" * (padded_length - len(plaintext))
    ciphertext = _chacha20(chacha_key, chacha_nonce, padded)
    mac = hmac.new(hmac_key, nonce + ciphertext, hashlib.sha256).digest()
    return base64.b64encode(bytes((_VERSION,)) + nonce + ciphertext + mac).decode(
        "ascii"
    )


def nip44_v2_encrypt(
    plaintext: str, secret_key: bytes, recipient_public_key_x: bytes
) -> str:
    """Encrypt UTF-8 text as a NIP-44 v2 payload using a fresh CSPRNG nonce.

    Callers handling untrusted or potentially large inputs should enforce their
    application-level byte limit before invoking this protocol primitive.
    """
    if not isinstance(plaintext, str):
        raise TypeError("plaintext must be str")
    try:
        plaintext_bytes = plaintext.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("plaintext is not valid UTF-8 text") from exc
    if not 1 <= len(plaintext_bytes) <= MAX_PLAINTEXT_SIZE:
        raise ValueError("plaintext length is outside the NIP-44 v2 range")

    conversation_key = nip44_v2_conversation_key(secret_key, recipient_public_key_x)
    return _encrypt_with_nonce(
        plaintext_bytes, conversation_key, secrets.token_bytes(_NONCE_SIZE)
    )


def _decrypt_with_conversation_key(payload: str, conversation_key: bytes) -> bytes:
    if not isinstance(payload, str):
        raise TypeError("payload must be str")
    try:
        encoded = payload.encode("ascii")
        data = base64.b64decode(encoded, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise ValueError("invalid NIP-44 v2 payload encoding") from exc

    # version + nonce + 2-byte prefix + 32-byte minimum padded plaintext + MAC
    if len(data) < 1 + _NONCE_SIZE + 2 + 32 + _MAC_SIZE:
        raise ValueError("NIP-44 v2 payload is too short")
    if data[0] != _VERSION:
        raise ValueError("unsupported NIP-44 payload version")

    nonce = data[1 : 1 + _NONCE_SIZE]
    ciphertext = data[1 + _NONCE_SIZE : -_MAC_SIZE]
    mac = data[-_MAC_SIZE:]
    chacha_key, chacha_nonce, hmac_key = _derive_message_keys(conversation_key, nonce)
    expected_mac = hmac.new(hmac_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("NIP-44 v2 authentication failed")

    padded = _chacha20(chacha_key, chacha_nonce, ciphertext)
    if len(padded) < 2:
        raise ValueError("invalid NIP-44 v2 padding")
    short_length = int.from_bytes(padded[:2], "big")
    if short_length == 0:
        if len(padded) < 6:
            raise ValueError("invalid NIP-44 v2 extended length prefix")
        plaintext_length = int.from_bytes(padded[2:6], "big")
        prefix_length = 6
        if plaintext_length < 65_536:
            raise ValueError("non-canonical NIP-44 v2 extended length")
    else:
        plaintext_length = short_length
        prefix_length = 2

    padded_length = calc_padded_length(plaintext_length)
    if len(padded) != prefix_length + padded_length:
        raise ValueError("invalid NIP-44 v2 ciphertext length")
    end = prefix_length + plaintext_length
    if any(padded[end:]):
        raise ValueError("invalid NIP-44 v2 zero padding")
    return padded[prefix_length:end]


def nip44_v2_decrypt(
    payload: str, secret_key: bytes, sender_public_key_x: bytes
) -> str:
    """Authenticate and decrypt a NIP-44 v2 payload to UTF-8 text.

    The caller must enforce its application-level event/payload size limit
    before handing an untrusted event to this protocol primitive.
    """
    conversation_key = nip44_v2_conversation_key(secret_key, sender_public_key_x)
    plaintext = _decrypt_with_conversation_key(payload, conversation_key)
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("NIP-44 v2 plaintext is not valid UTF-8") from exc

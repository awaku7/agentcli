"""bitchat_noise: Noise XX handshake and encryption for pybitchat DM.

Wire-compatible with the official bitchat app (Noise_XX_25519_ChaChaPoly_SHA256).
"""

from __future__ import annotations

import hashlib
import os as _os
from typing import Any

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

_PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"
# Noise protocol initialization: names <= HASHLEN are zero-padded, not hashed.
# This name is exactly 32 bytes, so Android's Noise implementation uses it
# directly as h and ck.
_PROTOCOL_NAME_HASH = (
    _PROTOCOL_NAME.ljust(32, b"\x00")
    if len(_PROTOCOL_NAME) <= 32
    else hashlib.sha256(_PROTOCOL_NAME).digest()
)
_ZEROLEN = b""

_DEBUG = _os.environ.get("UAGENT_BITCHAT_DEBUG", "") == "1"


def _dbg(msg: str) -> None:
    """Print a debug message only when UAGENT_BITCHAT_DEBUG=1."""
    if _DEBUG:
        print(msg, flush=True)


import hmac as _hmac_mod


def _hmac(key: bytes, data: bytes) -> bytes:
    return _hmac_mod.new(key, data, hashlib.sha256).digest()


def _hkdf(
    chaining_key: bytes, input_key_material: bytes, num_outputs: int
) -> list[bytes]:
    """Noise HKDF: HMAC-SHA256 based, returns num_outputs keys."""
    # temp_key = HMAC(chaining_key, input_key_material)
    temp_key = _hmac(chaining_key, input_key_material)
    # output1 = HMAC(temp_key, 0x01)
    output1 = _hmac(temp_key, b"\x01")
    if num_outputs == 1:
        return [output1]
    # output2 = HMAC(temp_key, output1 || 0x02)
    output2 = _hmac(temp_key, output1 + b"\x02")
    if num_outputs == 2:
        return [output1, output2]
    output3 = _hmac(temp_key, output2 + b"\x03")
    return [output1, output2, output3]


class NoiseCipherState:
    """A single cipher state (ChaCha20-Poly1305 with a nonce counter)."""

    def __init__(self, key: bytes):
        self._cipher = ChaCha20Poly1305(key)
        self._n = 0
        self._msg_count = 0
        self._max_msgs = 10000

    def _nonce_bytes(self) -> bytes:
        """96-bit nonce compatible with noise-java/southernstorm (Android).

        Android ChaChaPolyCipherState builds the 96-bit nonce as:
        [4 zero bytes][64-bit little-endian counter].  The Noise handshake
        always uses nonce=0 so this only matters for transport encryption.
        """
        return b"\x00\x00\x00\x00" + self._n.to_bytes(8, "little")

    def encrypt_with_ad(self, ad: bytes, plaintext: bytes) -> bytes:
        nonce = self._nonce_bytes()
        self._n += 1
        self._msg_count += 1
        return self._cipher.encrypt(nonce, plaintext, ad)

    def decrypt_with_ad(self, ad: bytes, ciphertext: bytes) -> bytes:
        nonce = self._nonce_bytes()
        self._n += 1
        return self._cipher.decrypt(nonce, ciphertext, ad)

    def set_nonce(self, n: int) -> None:
        """Set the cipher counter (used for Android's explicit-nonce transport)."""
        self._n = int(n)

    def rekey(self) -> None:
        """Rekey by encrypting zeros with current key (first 32 bytes)."""
        raw = self._cipher.encrypt(b"\x00" * 12, b"\x00" * 32, b"")
        new_key = raw[:32]
        self._cipher = ChaCha20Poly1305(new_key)
        self._msg_count = 0

    def nonce(self) -> int:
        return self._n

    @property
    def msg_count(self) -> int:
        return self._msg_count


class NoiseHandshakeState:
    """Noise XX handshake state machine.

    Provides process_message() to handle each XX handshake message.
    """

    def __init__(
        self,
        initiator: bool,
        s: X25519PrivateKey,  # local static key
        rs_pub: bytes | None = None,  # remote static public key (from announce)
    ):
        self.initiator = initiator
        self.s = s
        self.s_pub = s.public_key().public_bytes_raw()
        self.rs = rs_pub  # remote static pubkey bytes (32)

        # Handshake state
        self.h = _PROTOCOL_NAME_HASH
        self.ck = _PROTOCOL_NAME_HASH
        self.e: X25519PrivateKey | None = None  # local ephemeral
        self.re: bytes | None = None  # remote ephemeral pubkey
        self._cipher: Any = None  # current cipher state for encrypt/decrypt
        self._finished = False

        # Cipher states derived after handshake
        self.send_cipher: NoiseCipherState | None = None
        self.recv_cipher: NoiseCipherState | None = None

    def _mix_hash(self, data: bytes) -> None:
        self.h = hashlib.sha256(self.h + data).digest()

    def _mix_key(self, dh_result: bytes) -> None:
        outputs = _hkdf(self.ck, dh_result, 2)
        self.ck = outputs[0]
        temp_k = outputs[1]
        self._cipher = ChaCha20Poly1305(temp_k)

    def _encrypt_and_hash(self, plaintext: bytes) -> bytes:
        """Encrypt with current cipher and MixHash the ciphertext."""
        nonce = (0).to_bytes(12, "little")
        ct = self._cipher.encrypt(nonce, plaintext, self.h)
        self._mix_hash(ct)
        return ct

    def _decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        """Decrypt with current cipher and MixHash the ciphertext."""
        nonce = (0).to_bytes(12, "little")
        pt = self._cipher.decrypt(nonce, ciphertext, self.h)
        self._mix_hash(ciphertext)
        return pt

    def build_message_1(self) -> bytes:
        """Initiator builds handshake message 1: -> e"""
        self.e = X25519PrivateKey.generate()
        e_pub = self.e.public_key().public_bytes_raw()
        self._mix_hash(e_pub)
        # In Noise XX, the message payload after tokens is empty
        # Return just the e_pubkey (32 bytes)
        return e_pub

    def build_message_2(self) -> bytes:
        """Responder builds handshake message 2: <- e, ee, s, es

        Assumes re (remote ephemeral from msg1) is already set via process_message_1().
        """
        # Generate ephemeral
        self.e = X25519PrivateKey.generate()
        e_pub = self.e.public_key().public_bytes_raw()

        # e token: MixHash(e_pub) FIRST (Noise XX: -> e, ee, s, es)
        self._mix_hash(e_pub)

        # ee token: DH(re, e) -> MixKey
        re_key = X25519PublicKey.from_public_bytes(self.re)
        ee = self.e.exchange(re_key)
        self._mix_key(ee)

        # s token: encrypt own static key with the cipher derived from ee
        encrypted_s = self._encrypt_and_hash(self.s_pub)

        # es token: DH(own static, remote ephemeral) AFTER encrypting s
        es = self.s.exchange(re_key)
        self._mix_key(es)

        return e_pub + encrypted_s  # 32 + 48 = 80 bytes

    def build_message_3(self) -> bytes:
        """Initiator builds handshake message 3: -> s, se

        Assumes re (remote ephemeral from msg2) is already set via process_message_2().
        """
        # s token: encrypt own static key with the current cipher (from es)
        encrypted_s = self._encrypt_and_hash(self.s_pub)

        # se token: DH(own static, remote ephemeral) AFTER encrypting s
        re_key = X25519PublicKey.from_public_bytes(self.re)
        se = self.s.exchange(re_key)
        self._mix_key(se)

        # Split into send/recv cipher states
        self._split()

        return encrypted_s  # 48 bytes

    def _split(self) -> None:
        """Derive send/recv cipher states from chaining key."""
        outputs = _hkdf(self.ck, _ZEROLEN, 2)
        if self.initiator:
            self.send_cipher = NoiseCipherState(outputs[0])
            self.recv_cipher = NoiseCipherState(outputs[1])
        else:
            self.send_cipher = NoiseCipherState(outputs[1])
            self.recv_cipher = NoiseCipherState(outputs[0])
        self._finished = True

    def process_message_1(self, data: bytes) -> bool:
        """Responder processes handshake message 1: -> e"""
        if len(data) < 32:
            return False
        self.re = data[:32]
        self._mix_hash(self.re)
        return True

    def process_message_2(self, data: bytes) -> bool:
        """Initiator processes handshake message 2: <- e, ee, s, es"""
        if len(data) < 80:  # 32 e_pub + 48 encrypted_s
            _dbg("[bitchat] [debug] HS: msg2 too short: %d" % len(data))
            return False

        e_pub = data[:32]
        encrypted_s = data[32:80]

        # Set remote ephemeral
        self.re = e_pub
        self._mix_hash(e_pub)

        # ee = DH(e, re)
        e_key = X25519PrivateKey.from_private_bytes(self.e.private_bytes_raw())
        re_key = X25519PublicKey.from_public_bytes(self.re)
        ee = e_key.exchange(re_key)
        self._mix_key(ee)

        # Decrypt the remote static key with the cipher derived from ee
        try:
            remote_s = self._decrypt_and_hash(encrypted_s)
        except Exception as exc:
            _dbg("[bitchat] [debug] HS: msg2 decrypt FAILED: %r" % (exc,))
            _dbg("[bitchat] [debug] HS: msg2 e_pub=%s" % e_pub.hex())
            _dbg("[bitchat] [debug] HS: msg2 s_enc=%s" % encrypted_s.hex())
            _dbg("[bitchat] [debug] HS: msg2 h=%s" % self.h.hex())
            return False

        # es = DH(e, rs) AFTER decrypting s
        if self.rs is None:
            _dbg("[bitchat] [debug] HS: msg2 rs is None")
            return False
        rs_key = X25519PublicKey.from_public_bytes(self.rs)
        es = e_key.exchange(rs_key)
        self._mix_key(es)

        if remote_s != self.rs:
            _dbg("[bitchat] [debug] HS: msg2 rs mismatch")
            _dbg("[bitchat] [debug] HS:   remote_s=%s" % remote_s.hex())
            _dbg("[bitchat] [debug] HS:   self.rs =%s" % self.rs.hex())
            return False
        return True

    def process_message_3(self, data: bytes) -> bool:
        """Responder processes handshake message 3: -> s, se"""
        if len(data) < 48:
            _dbg("[bitchat] [debug] HS: msg3 too short: %d" % len(data))
            return False

        encrypted_s = data[:48]

        # Decrypt the remote static key with the current cipher
        try:
            remote_s = self._decrypt_and_hash(encrypted_s)
        except Exception as exc:
            # Keep the failure actionable without logging key material.
            _dbg(
                "[bitchat] [debug] HS: msg3 decrypt FAILED: %s h=%s"
                % (type(exc).__name__, self.h.hex())
            )
            return False

        # se = DH(e, rs) AFTER decrypting s
        if self.rs is None:
            return False
        rs_key = X25519PublicKey.from_public_bytes(self.rs)
        se = self.e.exchange(rs_key)
        self._mix_key(se)

        if remote_s != self.rs:
            _dbg("[bitchat] [debug] HS: msg3 static-key mismatch")
            return False

        # Split
        self._split()
        return True


# ---- Session management ---------------------------------------------------

_NOISE_SESSIONS: dict[str, NoiseHandshakeState] = {}
_NOISE_PENDING: dict[str, NoiseHandshakeState] = {}


def get_or_create_session(
    peer_id: str,
    initiator: bool,
    our_static: X25519PrivateKey,
    their_static_pub: bytes | None,
) -> NoiseHandshakeState | None:
    """Get existing session or create a new handshake state."""
    if peer_id in _NOISE_SESSIONS:
        return _NOISE_SESSIONS[peer_id]
    if peer_id in _NOISE_PENDING:
        return _NOISE_PENDING[peer_id]
    if initiator and their_static_pub is None:
        return None
    state = NoiseHandshakeState(initiator, our_static, their_static_pub)
    _NOISE_PENDING[peer_id] = state
    return state


def complete_session(peer_id: str, state: NoiseHandshakeState) -> None:
    """Move pending session to established."""
    _NOISE_PENDING.pop(peer_id, None)
    _NOISE_SESSIONS[peer_id] = state


def get_session(peer_id: str) -> NoiseHandshakeState | None:
    return _NOISE_SESSIONS.get(peer_id)


def remove_session(peer_id: str) -> None:
    _NOISE_SESSIONS.pop(peer_id, None)
    _NOISE_PENDING.pop(peer_id, None)


def encrypt_dm(session: NoiseHandshakeState, plaintext: bytes) -> bytes | None:
    """Encrypt a DM payload using an established Noise session (send cipher).

    Returns ciphertext suitable for NOISE_ENCRYPTED packet payload.
    """
    if session.send_cipher is None:
        return None
    try:
        # Android transport format: <nonce 4B big-endian><ciphertext>
        n = session.send_cipher.nonce()
        ct = session.send_cipher.encrypt_with_ad(_ZEROLEN, plaintext)
        return n.to_bytes(4, "big") + ct
    except Exception:
        return None


def decrypt_dm(session: NoiseHandshakeState, ciphertext: bytes) -> bytes | None:
    """Decrypt a DM payload using an established Noise session (recv cipher)."""
    if session.recv_cipher is None:
        return None
    try:
        # Android transport format: <nonce 4B big-endian><ciphertext>
        if len(ciphertext) < 4:
            return None
        n = int.from_bytes(ciphertext[:4], "big")
        ct = ciphertext[4:]
        session.recv_cipher.set_nonce(n)
        return session.recv_cipher.decrypt_with_ad(_ZEROLEN, ct)
    except Exception:
        return None


# ---- Private message TLV (Android/iOS PrivateMessagePacket compatible) ----

# NoisePayload types (Android NoiseEncrypted.kt)
_NOISE_PAYLOAD_PRIVATE_MESSAGE = 0x01
_NOISE_PAYLOAD_READ_RECEIPT = 0x02
_NOISE_PAYLOAD_DELIVERED = 0x03

# PrivateMessagePacket TLV types
_TLV_MESSAGE_ID = 0x00
_TLV_CONTENT = 0x01


def encode_private_message(message_id: str, content: str) -> bytes | None:
    """Encode a DM as Android/iOS NoisePayload + PrivateMessagePacket TLV.

    Format: [0x01][TLV: [0x00][len][msgID][0x01][len][content]]
    len is a single byte (max 255), matching Android PrivateMessagePacket.
    """
    try:
        mid = message_id.encode("utf-8")
        body = content.encode("utf-8")
        if len(mid) > 255 or len(body) > 255:
            return None
        tlv = (
            bytes([_TLV_MESSAGE_ID, len(mid)])
            + mid
            + bytes([_TLV_CONTENT, len(body)])
            + body
        )
        return bytes([_NOISE_PAYLOAD_PRIVATE_MESSAGE]) + tlv
    except Exception:
        return None


def decode_private_message(data: bytes) -> tuple[str, str] | None:
    """Decode NoisePayload + TLV to (message_id, content).

    Returns None for non-PRIVATE_MESSAGE payloads (ACK/read receipt etc.)
    or malformed data.
    """
    if not data:
        return None
    if data[0] != _NOISE_PAYLOAD_PRIVATE_MESSAGE:
        return None
    tlv = data[1:]
    offset = 0
    msg_id: str | None = None
    content: str | None = None
    while offset + 2 <= len(tlv):
        t = tlv[offset]
        ln = tlv[offset + 1]
        offset += 2
        if offset + ln > len(tlv):
            return None
        val = tlv[offset : offset + ln]
        offset += ln
        if t == _TLV_MESSAGE_ID:
            msg_id = val.decode("utf-8", errors="replace")
        elif t == _TLV_CONTENT:
            content = val.decode("utf-8", errors="replace")
    if msg_id is not None and content is not None:
        return msg_id, content
    return None

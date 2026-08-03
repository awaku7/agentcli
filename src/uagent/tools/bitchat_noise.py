"""bitchat_noise: Noise XX handshake and encryption for pybitchat DM.

Wire-compatible with the official bitchat app (Noise_XX_25519_ChaChaPoly_SHA256).
"""

from __future__ import annotations

import hashlib
import os as _os
import threading
import time
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305


def _raw_public_key(key: X25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def _raw_private_key(key: X25519PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )


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
_HANDSHAKE_TIMEOUT_SECONDS = 20.0
_SESSION_TIMEOUT_SECONDS = 24.0 * 60.0 * 60.0
_REPLAY_WINDOW_SIZE = 1024

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
        self._max_msgs = 1_000_000_000
        self._highest_received_nonce = -1
        self._received_nonces: set[int] = set()

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
        plaintext = self._cipher.decrypt(nonce, ciphertext, ad)
        # Do not consume a transport nonce when authentication fails.
        self._n += 1
        return plaintext

    def decrypt_with_ad_at_nonce(
        self, nonce_value: int, ad: bytes, ciphertext: bytes
    ) -> bytes:
        nonce = b"\x00\x00\x00\x00" + int(nonce_value).to_bytes(8, "little")
        return self._cipher.decrypt(nonce, ciphertext, ad)

    def is_valid_received_nonce(self, nonce: int) -> bool:
        """Return whether an extracted nonce is inside the replay window."""
        nonce = int(nonce)
        if nonce < 0:
            return False
        if self._highest_received_nonce >= 0:
            if nonce + _REPLAY_WINDOW_SIZE <= self._highest_received_nonce:
                return False
            if nonce <= self._highest_received_nonce and nonce in self._received_nonces:
                return False
        return True

    def mark_received_nonce(self, nonce: int) -> None:
        """Record a successfully authenticated extracted nonce."""
        nonce = int(nonce)
        if nonce > self._highest_received_nonce:
            self._highest_received_nonce = nonce
        self._received_nonces.add(nonce)
        floor = self._highest_received_nonce - (_REPLAY_WINDOW_SIZE - 1)
        self._received_nonces = {
            value for value in self._received_nonces if value >= floor
        }

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
        self.s_pub = _raw_public_key(s)
        self.rs = rs_pub  # remote static pubkey bytes (32)

        # Handshake state
        self.h = _PROTOCOL_NAME_HASH
        self.ck = _PROTOCOL_NAME_HASH
        # HandshakeState.start() always MixHash(prologue), including an empty
        # prologue. Southern Storm's implementation therefore hashes h once
        # before message 1; omitting this makes Android msg2 fail authentication.
        self._mix_hash(_ZEROLEN)
        self.e: X25519PrivateKey | None = None  # local ephemeral
        self.re: bytes | None = None  # remote ephemeral pubkey
        self._cipher: Any = None  # current cipher state for encrypt/decrypt
        self._finished = False
        self.created_at = time.monotonic()
        self.established_at: float | None = None

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
        e_pub = _raw_public_key(self.e)
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
        e_pub = _raw_public_key(self.e)

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

        # Noise encrypts the empty handshake payload after the tokens.
        encrypted_payload = self._encrypt_and_hash(_ZEROLEN)
        return e_pub + encrypted_s + encrypted_payload  # 32 + 48 + 16 = 96 bytes

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

        # Encrypt the empty handshake payload before splitting transport keys.
        encrypted_payload = self._encrypt_and_hash(_ZEROLEN)
        self._split()

        return encrypted_s + encrypted_payload  # 48 + 16 = 64 bytes

    def is_pending_expired(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return (
            self.established_at is None
            and now - self.created_at > _HANDSHAKE_TIMEOUT_SECONDS
        )

    def is_session_expired(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return (
            self.established_at is not None
            and now - self.established_at > _SESSION_TIMEOUT_SECONDS
        )

    def _split(self) -> None:
        """Derive send/recv cipher states from chaining key."""
        outputs = _hkdf(self.ck, _ZEROLEN, 2)
        if self.initiator:
            self.send_cipher = NoiseCipherState(outputs[0])
            self.recv_cipher = NoiseCipherState(outputs[1])
        else:
            self.send_cipher = NoiseCipherState(outputs[1])
            self.recv_cipher = NoiseCipherState(outputs[0])
        self.established_at = time.monotonic()
        self._finished = True

    def process_message_1(self, data: bytes) -> bool:
        """Responder processes handshake message 1: -> e"""
        if len(data) != 32:
            return False
        self.re = data
        self._mix_hash(self.re)
        return True

    def process_message_2(self, data: bytes) -> bool:
        """Initiator processes handshake message 2: <- e, ee, s, es"""
        if len(data) != 96:  # 32 e_pub + 48 encrypted_s + 16 empty payload tag
            _dbg("[bitchat] [debug] HS: msg2 invalid length: %d" % len(data))
            return False

        e_pub = data[:32]
        encrypted_s = data[32:80]

        # Set remote ephemeral
        self.re = e_pub
        self._mix_hash(e_pub)

        # ee = DH(e, re)
        e_key = X25519PrivateKey.from_private_bytes(_raw_private_key(self.e))
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
        try:
            self._decrypt_and_hash(data[80:])
        except Exception:
            _dbg("[bitchat] [debug] HS: msg2 empty payload authentication failed")
            return False

        if remote_s != self.rs:
            _dbg("[bitchat] [debug] HS: msg2 rs mismatch")
            _dbg("[bitchat] [debug] HS:   remote_s=%s" % remote_s.hex())
            _dbg("[bitchat] [debug] HS:   self.rs =%s" % self.rs.hex())
            return False
        return True

    def process_message_3(self, data: bytes) -> bool:
        """Responder processes handshake message 3: -> s, se"""
        if len(data) != 64:
            _dbg("[bitchat] [debug] HS: msg3 invalid length: %d" % len(data))
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
        try:
            self._decrypt_and_hash(data[48:])
        except Exception:
            _dbg("[bitchat] [debug] HS: msg3 empty payload authentication failed")
            return False

        if remote_s != self.rs:
            _dbg("[bitchat] [debug] HS: msg3 static-key mismatch")
            return False

        # Split
        self._split()
        return True


# ---- Session management ---------------------------------------------------

_NOISE_SESSIONS: dict[str, NoiseHandshakeState] = {}
_NOISE_PENDING: dict[str, NoiseHandshakeState] = {}
_NOISE_LOCK = threading.RLock()


def _purge_expired_locked(now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    for peer_id, state in list(_NOISE_PENDING.items()):
        if state.is_pending_expired(now):
            _NOISE_PENDING.pop(peer_id, None)
    for peer_id, state in list(_NOISE_SESSIONS.items()):
        if state.is_session_expired(now):
            _NOISE_SESSIONS.pop(peer_id, None)


def get_or_create_session(
    peer_id: str,
    initiator: bool,
    our_static: X25519PrivateKey,
    their_static_pub: bytes | None,
    *,
    force_new: bool = False,
) -> NoiseHandshakeState | None:
    """Get an unexpired session or create a fresh handshake state."""
    with _NOISE_LOCK:
        _purge_expired_locked()
        if force_new:
            _NOISE_PENDING.pop(peer_id, None)
        if peer_id in _NOISE_SESSIONS:
            return _NOISE_SESSIONS[peer_id]
        if peer_id in _NOISE_PENDING:
            return _NOISE_PENDING[peer_id]
        if initiator and their_static_pub is None:
            return None
        state = NoiseHandshakeState(initiator, our_static, their_static_pub)
        _NOISE_PENDING[peer_id] = state
        return state


def get_pending_session(peer_id: str) -> NoiseHandshakeState | None:
    with _NOISE_LOCK:
        _purge_expired_locked()
        return _NOISE_PENDING.get(peer_id)


def set_pending_session(peer_id: str, state: NoiseHandshakeState) -> None:
    with _NOISE_LOCK:
        _NOISE_PENDING[peer_id] = state


def complete_session(peer_id: str, state: NoiseHandshakeState) -> None:
    """Move pending session to established."""
    with _NOISE_LOCK:
        _purge_expired_locked()
        _NOISE_PENDING.pop(peer_id, None)
        _NOISE_SESSIONS[peer_id] = state


def get_session(peer_id: str) -> NoiseHandshakeState | None:
    with _NOISE_LOCK:
        _purge_expired_locked()
        return _NOISE_SESSIONS.get(peer_id)


def remove_session(peer_id: str) -> None:
    with _NOISE_LOCK:
        _NOISE_SESSIONS.pop(peer_id, None)
        _NOISE_PENDING.pop(peer_id, None)


def clear_sessions() -> None:
    with _NOISE_LOCK:
        _NOISE_SESSIONS.clear()
        _NOISE_PENDING.clear()


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
        if not session.recv_cipher.is_valid_received_nonce(n):
            return None
        try:
            plaintext = session.recv_cipher.decrypt_with_ad_at_nonce(n, _ZEROLEN, ct)
        except Exception:
            return None
        session.recv_cipher.mark_received_nonce(n)
        return plaintext
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

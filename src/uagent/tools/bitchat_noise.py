"""bitchat_noise: Noise XX handshake and encryption for pybitchat DM.

Wire-compatible with the official bitchat app (Noise_XX_25519_ChaChaPoly_SHA256).
"""

from __future__ import annotations

import hashlib
from typing import Any

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

_PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"
_PROTOCOL_NAME_HASH = hashlib.sha256(_PROTOCOL_NAME).digest()
_ZEROLEN = b""


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

    def encrypt_with_ad(self, ad: bytes, plaintext: bytes) -> bytes:
        nonce = self._n.to_bytes(12, "little")
        self._n += 1
        self._msg_count += 1
        return self._cipher.encrypt(nonce, plaintext, ad)

    def decrypt_with_ad(self, ad: bytes, ciphertext: bytes) -> bytes:
        nonce = self._n.to_bytes(12, "little")
        self._n += 1
        return self._cipher.decrypt(nonce, ciphertext, ad)

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

        # ee = DH(re, e)
        re_key = X25519PublicKey.from_public_bytes(self.re)
        ee = self.e.exchange(re_key)
        self._mix_key(ee)

        # es = DH(re, s)
        es = self.s.exchange(re_key)
        self._mix_key(es)

        # Append e_pub
        self._mix_hash(e_pub)

        # Encrypt static public key
        encrypted_s = self._encrypt_and_hash(self.s_pub)

        return e_pub + encrypted_s  # 32 + 48 = 80 bytes

    def build_message_3(self) -> bytes:
        """Initiator builds handshake message 3: -> s, se

        Assumes re (remote ephemeral from msg2) is already set via process_message_2().
        """
        # se = DH(s, re)
        re_key = X25519PublicKey.from_public_bytes(self.re)
        se = self.s.exchange(re_key)
        self._mix_key(se)

        # Encrypt static public key
        encrypted_s = self._encrypt_and_hash(self.s_pub)

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

        # es = DH(e, rs)  - we need the remote static key from announce
        if self.rs is None:
            return False
        rs_key = X25519PublicKey.from_public_bytes(self.rs)
        es = e_key.exchange(rs_key)
        self._mix_key(es)

        # Decrypt static key (but we already know it from announce)
        try:
            self._decrypt_and_hash(encrypted_s)
        except Exception:
            return False

        return True

    def process_message_3(self, data: bytes) -> bool:
        """Responder processes handshake message 3: -> s, se"""
        if len(data) < 48:
            return False

        encrypted_s = data[:48]

        # se = DH(e, rs)  - we need remote static pubkey
        if self.rs is None:
            return False
        rs_key = X25519PublicKey.from_public_bytes(self.rs)
        se = self.e.exchange(rs_key)
        self._mix_key(se)

        # Decrypt and verify static key
        try:
            remote_s = self._decrypt_and_hash(encrypted_s)
            if remote_s != self.rs:
                return False
        except Exception:
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
        # In Noise transport mode, encrypt with AD = zerolen (no additional data in packet)
        return session.send_cipher.encrypt_with_ad(_ZEROLEN, plaintext)
    except Exception:
        return None


def decrypt_dm(session: NoiseHandshakeState, ciphertext: bytes) -> bytes | None:
    """Decrypt a DM payload using an established Noise session (recv cipher)."""
    if session.recv_cipher is None:
        return None
    try:
        return session.recv_cipher.decrypt_with_ad(_ZEROLEN, ciphertext)
    except Exception:
        return None

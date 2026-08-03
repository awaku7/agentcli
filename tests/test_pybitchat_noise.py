"""Tests for the active BitChat Noise XX implementation."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from uagent.tools.bitchat_noise import (
    NoiseCipherState,
    NoiseHandshakeState,
    decrypt_dm,
    encrypt_dm,
)


def _public_bytes(key: X25519PrivateKey) -> bytes:
    from cryptography.hazmat.primitives import serialization

    return key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )


def _make_handshake_pair() -> tuple[NoiseHandshakeState, NoiseHandshakeState]:
    initiator_static = X25519PrivateKey.generate()
    responder_static = X25519PrivateKey.generate()
    initiator = NoiseHandshakeState(
        True, initiator_static, _public_bytes(responder_static)
    )
    responder = NoiseHandshakeState(
        False, responder_static, _public_bytes(initiator_static)
    )

    message1 = initiator.build_message_1()
    assert responder.process_message_1(message1)
    message2 = responder.build_message_2()
    assert initiator.process_message_2(message2)
    message3 = initiator.build_message_3()
    assert responder.process_message_3(message3)
    return initiator, responder


class TestNoiseXXHandshake:
    def test_wire_lengths_include_empty_payload_tags(self) -> None:
        initiator_static = X25519PrivateKey.generate()
        responder_static = X25519PrivateKey.generate()
        initiator = NoiseHandshakeState(
            True, initiator_static, _public_bytes(responder_static)
        )
        responder = NoiseHandshakeState(
            False, responder_static, _public_bytes(initiator_static)
        )

        message1 = initiator.build_message_1()
        assert len(message1) == 32
        assert responder.process_message_1(message1)

        message2 = responder.build_message_2()
        assert len(message2) == 96
        assert initiator.process_message_2(message2)

        message3 = initiator.build_message_3()
        assert len(message3) == 64
        assert responder.process_message_3(message3)

    def test_full_handshake_derives_opposite_transport_keys(self) -> None:
        initiator, responder = _make_handshake_pair()
        assert initiator.send_cipher is not None
        assert initiator.recv_cipher is not None
        assert responder.send_cipher is not None
        assert responder.recv_cipher is not None
        outgoing = initiator.send_cipher.encrypt_with_ad(b"", b"outgoing")
        assert responder.recv_cipher.decrypt_with_ad(b"", outgoing) == b"outgoing"
        reply = responder.send_cipher.encrypt_with_ad(b"", b"reply")
        assert initiator.recv_cipher.decrypt_with_ad(b"", reply) == b"reply"

    def test_tampered_empty_payload_tag_is_rejected(self) -> None:
        initiator_static = X25519PrivateKey.generate()
        responder_static = X25519PrivateKey.generate()
        initiator = NoiseHandshakeState(
            True, initiator_static, _public_bytes(responder_static)
        )
        responder = NoiseHandshakeState(
            False, responder_static, _public_bytes(initiator_static)
        )
        message1 = initiator.build_message_1()
        responder.process_message_1(message1)
        message2 = bytearray(responder.build_message_2())
        message2[-1] ^= 1
        assert not initiator.process_message_2(bytes(message2))


class TestNoiseTransport:
    def test_dm_roundtrip_uses_explicit_nonce(self) -> None:
        initiator, responder = _make_handshake_pair()
        plaintext = b"Hello BLE Mesh!"
        ciphertext = encrypt_dm(initiator, plaintext)
        assert ciphertext is not None
        assert decrypt_dm(responder, ciphertext) == plaintext

    def test_replayed_dm_is_rejected(self) -> None:
        initiator, responder = _make_handshake_pair()
        ciphertext = encrypt_dm(initiator, b"one-time")
        assert ciphertext is not None
        assert decrypt_dm(responder, ciphertext) == b"one-time"
        assert decrypt_dm(responder, ciphertext) is None

    def test_cipher_wrong_ad_fails(self) -> None:
        sender = NoiseCipherState(b"a" * 32)
        receiver = NoiseCipherState(b"a" * 32)
        ciphertext = sender.encrypt_with_ad(b"ad1", b"secret")
        with pytest.raises(Exception):
            receiver.decrypt_with_ad(b"ad2", ciphertext)

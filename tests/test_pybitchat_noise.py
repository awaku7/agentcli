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


class TestNoiseXXReferenceVectors:
    """Known-answer vectors produced by an independent Noise implementation
    (dissononce) for Noise_XX_25519_ChaChaPoly_SHA256 with an empty
    prologue and empty handshake payloads -- the exact profile the official
    BitChat clients (southernstorm) speak. A UAG-to-UAG handshake cannot
    catch a symmetric deviation from the spec; these bytes can. They pin
    two easy-to-miss rules: message 1's empty payload is still mixed into
    the handshake hash, and the handshake cipher nonce advances between
    message 2's payload and message 3's static key (same cipher state).
    """

    INITIATOR_STATIC = bytes.fromhex(
        "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"
    )
    RESPONDER_STATIC = bytes.fromhex(
        "2122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f40"
    )
    INITIATOR_EPHEMERAL = bytes.fromhex(
        "c0b8b5485c30190fc2da3cc6faea5e894f146b0761c2d156966ee5fbddb4037b"
    )
    RESPONDER_EPHEMERAL = bytes.fromhex(
        "28b96d30e82e49457b3a073cd50a59cb2e80f30a7d6679ec1ebb337cae8d0d41"
    )
    MESSAGE_1 = bytes.fromhex(
        "00ac3bebea4cfcc0d6512e446f9c6d7535e5b5be613e2605d3d3ce458b10202f"
    )
    MESSAGE_2 = bytes.fromhex(
        "86d63bf215f85ccf109ae25a09eb326dcc79905bf1e71cbd254422d128cdfe54"
        "6aa6d15018fe0083aa085f33bfd191442337ad8aee5532fa33afb1e3b3d63268"
        "99a995f61eccafe224c143e8556313129ddb39edb4b2a92c1e2721f2bcf6a231"
    )
    MESSAGE_3 = bytes.fromhex(
        "655b8301c2e0b2e87f082a1b47c9400d1538268ff10f965e90d85fe29f7d5846"
        "cd4794d3d9b6760abfdbe04c79dc8d8d8600e36ef534a1bda70d9e43c1e1563b"
    )
    CT_INITIATOR_HELLO = bytes.fromhex("6048a1febc00347f0b35b94b079ac2038b5cf91708")
    CT_RESPONDER_WORLD = bytes.fromhex("ef31ad3df481e4c77cbf0c88c75b4080c37dc1dfd3")

    def test_handshake_matches_reference_vectors(self, monkeypatch) -> None:
        initiator_static = X25519PrivateKey.from_private_bytes(self.INITIATOR_STATIC)
        responder_static = X25519PrivateKey.from_private_bytes(self.RESPONDER_STATIC)
        initiator = NoiseHandshakeState(
            True, initiator_static, _public_bytes(responder_static)
        )
        responder = NoiseHandshakeState(
            False, responder_static, _public_bytes(initiator_static)
        )
        ephemerals = iter(
            [
                X25519PrivateKey.from_private_bytes(self.INITIATOR_EPHEMERAL),
                X25519PrivateKey.from_private_bytes(self.RESPONDER_EPHEMERAL),
            ]
        )
        monkeypatch.setattr(
            X25519PrivateKey,
            "generate",
            classmethod(lambda cls: next(ephemerals)),
        )

        message1 = initiator.build_message_1()
        assert message1 == self.MESSAGE_1
        assert responder.process_message_1(message1)

        message2 = responder.build_message_2()
        assert message2 == self.MESSAGE_2
        assert initiator.process_message_2(message2)

        message3 = initiator.build_message_3()
        assert message3 == self.MESSAGE_3
        assert responder.process_message_3(message3)

        assert initiator.send_cipher is not None
        assert responder.send_cipher is not None
        assert (
            initiator.send_cipher.encrypt_with_ad(b"", b"hello")
            == self.CT_INITIATOR_HELLO
        )
        assert (
            responder.send_cipher.encrypt_with_ad(b"", b"world")
            == self.CT_RESPONDER_WORLD
        )

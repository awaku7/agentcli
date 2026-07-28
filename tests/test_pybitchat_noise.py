"""Phase 2 TDD: Noise XX ハンドシェイク."""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
import pytest


def _generate_keypair() -> tuple[bytes, bytes]:
    """Generate X25519 key pair, returns (private_bytes, public_bytes)."""
    private_key = x25519.X25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_bytes, public_bytes


class TestNoiseXXHandshake:
    """Noise XX ハンドシェイク状態機械のテスト."""

    def _make_noise(self):
        """Create a NoiseXXStateMachine instance."""
        from uagent.tools.pybitchat_shared import NoiseXXStateMachine

        s, s_pub = _generate_keypair()
        return NoiseXXStateMachine(
            static_private=s,
            static_public=s_pub,
            prologue=b"bitchat-noise-xx",
        )

    def test_init_generates_ephemeral(self) -> None:
        """process_message_1 でエフェメラル鍵が生成される."""
        noise = self._make_noise()
        noise.process_message_1()
        assert noise.e is not None
        assert len(noise.e) == 32

    def test_message_1_returns_bytes(self) -> None:
        """message 1 がバイト列を返す."""
        noise = self._make_noise()
        msg1 = noise.process_message_1()
        assert isinstance(msg1, bytes)
        assert len(msg1) > 0

    def test_full_handshake_roundtrip(self) -> None:
        """Initiator と Responder 間の完全な XX ハンドシェイク."""
        # 鍵生成
        init_s, init_s_pub = _generate_keypair()
        resp_s, resp_s_pub = _generate_keypair()

        from uagent.tools.pybitchat_shared import NoiseXXStateMachine

        initiator = NoiseXXStateMachine(
            static_private=init_s,
            static_public=init_s_pub,
            prologue=b"bitchat-noise-xx",
            initiator=True,
        )
        responder = NoiseXXStateMachine(
            static_private=resp_s,
            static_public=resp_s_pub,
            prologue=b"bitchat-noise-xx",
            initiator=False,
        )

        # -> message 1
        msg1 = initiator.process_message_1()
        assert msg1 is not None

        # <- message 2
        msg2 = responder.process_message_1(msg1)
        assert msg2 is not None

        # -> message 3
        msg3 = initiator.process_message_2(msg2)
        assert msg3 is not None

        # responder finalize
        responder.process_message_2(msg3)

        # 両者にトランスポート暗号が確立されている
        assert initiator.tx is not None
        assert initiator.rx is not None
        assert responder.tx is not None
        assert responder.rx is not None

        # tx/rx keys が対称になっている
        assert initiator.tx.k == responder.rx.k
        assert initiator.rx.k == responder.tx.k

    def test_handshake_with_known_keys(self) -> None:
        """既知の鍵ペアでハンドシェイクが再現可能."""
        # Fixed keys for reproducibility
        from uagent.tools.pybitchat_shared import NoiseXXStateMachine, _generate_keypair

        init_s, init_s_pub = _generate_keypair()
        resp_s, resp_s_pub = _generate_keypair()

        initiator = NoiseXXStateMachine(
            static_private=init_s,
            static_public=init_s_pub,
            prologue=b"bitchat-noise-xx",
            initiator=True,
        )
        responder = NoiseXXStateMachine(
            static_private=resp_s,
            static_public=resp_s_pub,
            prologue=b"bitchat-noise-xx",
            initiator=False,
        )

        msg1 = initiator.process_message_1()
        msg2 = responder.process_message_1(msg1)
        msg3 = initiator.process_message_2(msg2)
        responder.process_message_2(msg3)

        assert initiator.tx.k == responder.rx.k


class TestTransportCipher:
    """Noise トランスポート暗号のテスト."""

    def _make_ciphers(self):
        """Create a pair of transport ciphers (tx/rx)."""
        from uagent.tools.pybitchat_shared import (
            NoiseXXStateMachine,
            _generate_keypair as gk,
        )

        init_s, init_s_pub = gk()
        resp_s, resp_s_pub = gk()

        initiator = NoiseXXStateMachine(
            static_private=init_s,
            static_public=init_s_pub,
            prologue=b"bitchat-noise-xx",
            initiator=True,
        )
        responder = NoiseXXStateMachine(
            static_private=resp_s,
            static_public=resp_s_pub,
            prologue=b"bitchat-noise-xx",
            initiator=False,
        )

        msg1 = initiator.process_message_1()
        msg2 = responder.process_message_1(msg1)
        msg3 = initiator.process_message_2(msg2)
        responder.process_message_2(msg3)

        return initiator, responder

    def test_encrypt_decrypt(self) -> None:
        """暗号化→復号がラウンドトリップする."""
        initiator, responder = self._make_ciphers()

        # initiator -> responder
        plaintext = b"Hello BLE Mesh!"
        ciphertext = initiator.tx.encrypt_with_ad(b"", plaintext)
        decrypted = responder.rx.decrypt_with_ad(b"", ciphertext)
        assert decrypted == plaintext

    def test_encrypt_with_ad(self) -> None:
        """AD (associated data) 付き暗号化."""
        initiator, responder = self._make_ciphers()

        ad = b"\x00\x01\x02"
        plaintext = b"message with context"
        ciphertext = initiator.tx.encrypt_with_ad(ad, plaintext)
        decrypted = responder.rx.decrypt_with_ad(ad, ciphertext)
        assert decrypted == plaintext

    def test_encrypt_wrong_ad_fails(self) -> None:
        """AD が異なると復号に失敗する."""
        initiator, responder = self._make_ciphers()

        ciphertext = initiator.tx.encrypt_with_ad(b"ad1", b"secret")
        with pytest.raises(Exception):
            responder.rx.decrypt_with_ad(b"ad2", ciphertext)

    def test_nonce_advances(self) -> None:
        """nonce (n) が暗号化ごとにインクリメントされる."""
        initiator, responder = self._make_ciphers()

        n_before = initiator.tx.n
        initiator.tx.encrypt_with_ad(b"", b"msg1")
        assert initiator.tx.n == n_before + 1
        initiator.tx.encrypt_with_ad(b"", b"msg2")
        assert initiator.tx.n == n_before + 2

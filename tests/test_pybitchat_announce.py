"""Phase 3 TDD: Announce / Discovery のテスト."""

from __future__ import annotations

import time


from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


def _generate_signing_keypair() -> tuple[bytes, bytes]:
    """Generate Ed25519 key pair, returns (private_bytes, public_bytes)."""
    private_key = ed25519.Ed25519PrivateKey.generate()
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


class TestAnnounceSigning:
    """Announce パケットの署名と検証."""

    def test_sign_and_verify(self) -> None:
        """Announce に署名し、検証できる."""
        from uagent.tools.pybitchat_shared import (
            sign_announce,
            verify_announce,
        )

        sign_priv, sign_pub = _generate_signing_keypair()
        noise_pub = b"\x11" * 32

        announce_data = {
            "nickname": "testnode",
            "noise_public_key": noise_pub,
            "signing_public_key": sign_pub,
            "timestamp": int(time.time() * 1000),
        }

        signature = sign_announce(announce_data, sign_priv)
        assert len(signature) == 64  # Ed25519 signature

        # Verify
        result = verify_announce(announce_data, signature, sign_pub)
        assert result is True

    def test_verify_wrong_key_fails(self) -> None:
        """異なる公開鍵で検証すると失敗する."""
        from uagent.tools.pybitchat_shared import (
            sign_announce,
            verify_announce,
        )

        sign_priv, sign_pub = _generate_signing_keypair()
        _, wrong_pub = _generate_signing_keypair()
        noise_pub = b"\x11" * 32

        announce_data = {
            "nickname": "testnode",
            "noise_public_key": noise_pub,
            "signing_public_key": sign_pub,
            "timestamp": int(time.time() * 1000),
        }

        signature = sign_announce(announce_data, sign_priv)
        result = verify_announce(announce_data, signature, wrong_pub)
        assert result is False

    def test_verify_tampered_data_fails(self) -> None:
        """改ざんされたデータの検証は失敗する."""
        from uagent.tools.pybitchat_shared import (
            sign_announce,
            verify_announce,
        )

        sign_priv, sign_pub = _generate_signing_keypair()
        noise_pub = b"\x11" * 32

        announce_data = {
            "nickname": "testnode",
            "noise_public_key": noise_pub,
            "signing_public_key": sign_pub,
            "timestamp": int(time.time() * 1000),
        }

        signature = sign_announce(announce_data, sign_priv)

        # Tamper
        tampered = dict(announce_data)
        tampered["nickname"] = "evilnode"
        result = verify_announce(tampered, signature, sign_pub)
        assert result is False


class TestPeerRegistry:
    """ピアレジストリの管理."""

    def test_add_and_get_peer(self) -> None:
        """ピアを追加して取得できる."""
        from uagent.tools.pybitchat_shared import PeerRegistry

        registry = PeerRegistry()
        peer_id = "0123456789abcdef"

        registry.add_peer(
            peer_id=peer_id,
            nickname="Bob",
            noise_public_key=b"\x22" * 32,
            signing_public_key=b"\x33" * 32,
        )

        peer = registry.get_peer(peer_id)
        assert peer is not None
        assert peer["nickname"] == "Bob"
        assert peer["noise_public_key"] == b"\x22" * 32

    def test_get_unknown_peer(self) -> None:
        """存在しないピアは None を返す."""
        from uagent.tools.pybitchat_shared import PeerRegistry

        registry = PeerRegistry()
        assert registry.get_peer("nonexistent") is None

    def test_peer_list(self) -> None:
        """登録済みピアの一覧を取得できる."""
        from uagent.tools.pybitchat_shared import PeerRegistry

        registry = PeerRegistry()
        registry.add_peer("peer1", "Alice", b"\x11" * 32, b"\x22" * 32)
        registry.add_peer("peer2", "Bob", b"\x33" * 32, b"\x44" * 32)

        peers = registry.list_peers()
        assert len(peers) == 2

    def test_peer_ttl_expiry(self) -> None:
        """TTL 経過後はピアが除去される."""
        from uagent.tools.pybitchat_shared import PeerRegistry

        registry = PeerRegistry(ttl_seconds=0.1)  # 100ms TTL
        registry.add_peer("peer1", "Alice", b"\x11" * 32, b"\x22" * 32)
        assert registry.get_peer("peer1") is not None

        time.sleep(0.15)
        assert registry.get_peer("peer1") is None

    def test_peer_state_transitions(self) -> None:
        """ピアの接続状態管理."""
        from uagent.tools.pybitchat_shared import PeerRegistry

        registry = PeerRegistry()
        registry.add_peer("peer1", "Alice", b"\x11" * 32, b"\x22" * 32)

        # Default state
        assert registry.get_peer_state("peer1") == "discovered"

        # Transition
        registry.set_peer_state("peer1", "connected")
        assert registry.get_peer_state("peer1") == "connected"

        registry.set_peer_state("peer1", "disconnected")
        assert registry.get_peer_state("peer1") == "disconnected"

    def test_remove_peer(self) -> None:
        """ピアを削除できる."""
        from uagent.tools.pybitchat_shared import PeerRegistry

        registry = PeerRegistry()
        registry.add_peer("peer1", "Alice", b"\x11" * 32, b"\x22" * 32)
        assert registry.get_peer("peer1") is not None

        registry.remove_peer("peer1")
        assert registry.get_peer("peer1") is None

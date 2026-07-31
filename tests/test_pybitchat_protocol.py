"""Phase 1 TDD: bitchat-protocol パケットエンコード/デコードのテスト."""

from __future__ import annotations

import time

from bitchat_protocol import (
    AnnouncementPacket,
    BitchatPacket,
    MessageType,
    decode,
    decode_announcement,
    encode,
    encode_announcement,
)


def _dummy_sender_id() -> bytes:
    """8-byte dummy sender ID."""
    return b"\x01\x02\x03\x04\x05\x06\x07\x08"


def _dummy_recipient_id() -> bytes:
    """8-byte dummy recipient ID."""
    return b"\xff\xfe\xfd\xfc\xfb\xfa\xf9\xf8"


class TestBitchatPacketEncodeDecode:
    """BitchatPacket のエンコード→デコードのラウンドトリップ."""

    def test_minimal_packet(self) -> None:
        """最小構成のパケット（ペイロードのみ）."""
        packet = BitchatPacket(
            version=1,
            type=MessageType.MESSAGE.value,
            ttl=64,
            timestamp=int(time.time() * 1000),
            flags=0,
            sender_id=_dummy_sender_id(),
            payload=b"hello",
        )
        data = encode(packet)
        decoded = decode(data)
        assert decoded is not None
        assert decoded.version == packet.version
        assert decoded.type == packet.type
        assert decoded.ttl == packet.ttl
        assert decoded.payload == packet.payload
        assert decoded.sender_id == packet.sender_id

    def test_packet_with_recipient(self) -> None:
        """受信者指定ありのパケット."""
        packet = BitchatPacket(
            version=1,
            type=MessageType.MESSAGE.value,
            ttl=64,
            timestamp=int(time.time() * 1000),
            flags=0,
            sender_id=_dummy_sender_id(),
            payload=b"direct message",
            recipient_id=_dummy_recipient_id(),
        )
        data = encode(packet)
        decoded = decode(data)
        assert decoded is not None
        assert decoded.recipient_id == packet.recipient_id
        assert decoded.payload == b"direct message"

    def test_packet_with_padding(self) -> None:
        """パディング付きエンコード."""
        packet = BitchatPacket(
            version=1,
            type=MessageType.MESSAGE.value,
            ttl=64,
            timestamp=int(time.time() * 1000),
            flags=0,
            sender_id=_dummy_sender_id(),
            payload=b"padded",
        )
        data = encode(packet, padding=True)
        decoded = decode(data)
        assert decoded is not None
        assert decoded.payload == b"padded"

    def test_empty_payload(self) -> None:
        """空ペイロード."""
        packet = BitchatPacket(
            version=1,
            type=MessageType.MESSAGE.value,
            ttl=0,
            timestamp=0,
            flags=0,
            sender_id=_dummy_sender_id(),
            payload=b"",
        )
        data = encode(packet)
        decoded = decode(data)
        assert decoded is not None
        assert decoded.payload == b""

    def test_large_payload(self) -> None:
        """大きめのペイロード（4000 bytes）."""
        payload = b"X" * 4000
        packet = BitchatPacket(
            version=1,
            type=MessageType.MESSAGE.value,
            ttl=64,
            timestamp=int(time.time() * 1000),
            flags=0,
            sender_id=_dummy_sender_id(),
            payload=payload,
        )
        data = encode(packet)
        decoded = decode(data)
        assert decoded is not None
        assert decoded.payload == payload


class TestAnnouncementPacket:
    """AnnouncementPacket のエンコード/デコード."""

    def test_announce_minimal(self) -> None:
        """最小構成の Announce."""
        ann = AnnouncementPacket(
            nickname="testnode",
            noise_public_key=b"\x11" * 32,
            signing_public_key=b"\x22" * 32,
        )
        data = encode_announcement(ann)
        decoded = decode_announcement(data)
        assert decoded is not None
        assert decoded.nickname == "testnode"
        assert decoded.noise_public_key == b"\x11" * 32
        assert decoded.signing_public_key == b"\x22" * 32

    def test_announce_with_neighbors(self) -> None:
        """直接接続ピア情報付き Announce（peer_id は 8 bytes）."""
        ann = AnnouncementPacket(
            nickname="hubnode",
            noise_public_key=b"\x33" * 32,
            signing_public_key=b"\x44" * 32,
            direct_neighbors=[b"\xaa" * 8, b"\xbb" * 8],
        )
        data = encode_announcement(ann)
        decoded = decode_announcement(data)
        assert decoded is not None
        assert decoded.nickname == "hubnode"
        assert decoded.direct_neighbors is not None
        assert len(decoded.direct_neighbors) == 2

    def test_announce_invalid_data(self) -> None:
        """不正なデータは None を返す."""
        result = decode_announcement(b"\x00\x00\x00")
        assert result is None


class TestBitchatPacketEdgeCases:
    """エッジケース."""

    def test_decode_invalid_empty(self) -> None:
        """空バイト列は None を返す."""
        assert decode(b"") is None

    def test_decode_invalid_garbage(self) -> None:
        """不正なバイト列は None を返す."""
        assert decode(b"\xff\xff\xff\xff") is None

    def test_all_message_types(self) -> None:
        """全ての MessageType でエンコード/デコード."""
        for msg_type in MessageType:
            packet = BitchatPacket(
                version=1,
                type=msg_type.value,
                ttl=64,
                timestamp=int(time.time() * 1000),
                flags=0,
                sender_id=_dummy_sender_id(),
                payload=b"type test",
            )
            data = encode(packet)
            decoded = decode(data)
            assert decoded is not None
            assert decoded.type == msg_type.value

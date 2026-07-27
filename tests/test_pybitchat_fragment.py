"""Phase 5 TDD: フラグメンテーション."""

from __future__ import annotations

from uagent.tools.pybitchat_shared import FragmentAssemblyBuffer, FragmentHeader, parse_fragment_payload


def _payload(size: int) -> bytes:
    return b"x" * size


def _fid(n: int) -> bytes:
    """8-byte fragment ID derived from int."""
    return n.to_bytes(8, "big")


class TestFragmentAssemblyBuffer:
    """FragmentAssemblyBuffer のユニットテスト."""

    def test_single_fragment_message(self) -> None:
        """単一フラグメント（分割不要）."""
        buf = FragmentAssemblyBuffer()
        sender = b"\xaa" * 8
        header = FragmentHeader(fragment_id=_fid(1), fragment_index=0, total_fragments=1, message_type=2)
        result = buf.append(sender, header, b"hello")
        assert result == b"hello"

    def test_two_fragment_assembly(self) -> None:
        """2フラグメントの再構築."""
        buf = FragmentAssemblyBuffer()
        sender = b"\xaa" * 8
        h1 = FragmentHeader(fragment_id=_fid(1), fragment_index=0, total_fragments=2, message_type=2)
        h2 = FragmentHeader(fragment_id=_fid(1), fragment_index=1, total_fragments=2, message_type=2)
        assert buf.append(sender, h1, b"hel") is None
        result = buf.append(sender, h2, b"lo")
        assert result == b"hello"

    def test_out_of_order_assembly(self) -> None:
        """フラグメントが逆順でも再構築できる."""
        buf = FragmentAssemblyBuffer()
        sender = b"\xaa" * 8
        h1 = FragmentHeader(fragment_id=_fid(1), fragment_index=0, total_fragments=2, message_type=2)
        h2 = FragmentHeader(fragment_id=_fid(1), fragment_index=1, total_fragments=2, message_type=2)
        buf.append(sender, h2, b"lo")
        result = buf.append(sender, h1, b"hel")
        assert result == b"hello"

    def test_multiple_transfers_independent(self) -> None:
        """複数の転送が同時進行できる."""
        buf = FragmentAssemblyBuffer()
        sender = b"\xaa" * 8
        h1_0 = FragmentHeader(fragment_id=_fid(1), fragment_index=0, total_fragments=2, message_type=2)
        h1_1 = FragmentHeader(fragment_id=_fid(1), fragment_index=1, total_fragments=2, message_type=2)
        h2_0 = FragmentHeader(fragment_id=_fid(2), fragment_index=0, total_fragments=1, message_type=2)
        buf.append(sender, h2_0, b"alone")
        buf.append(sender, h1_0, b"he")
        result = buf.append(sender, h1_1, b"llo")
        assert result == b"hello"

    def test_expiry_removes_incomplete(self) -> None:
        """期限切れの不完全な転送を削除."""
        buf = FragmentAssemblyBuffer()
        sender = b"\xaa" * 8
        h = FragmentHeader(fragment_id=_fid(99), fragment_index=0, total_fragments=2, message_type=2)
        buf.append(sender, h, b"only_first")
        expired = buf.remove_expired(before=9999999999)
        assert len(expired) == 1
        assert expired[0] == (sender, _fid(99))
        assert buf.inflight_count() == 0

    def test_max_inflight_limit(self) -> None:
        """最大インフライト数を超えると拒否."""
        buf = FragmentAssemblyBuffer(max_inflight=2)
        sender = b"\xaa" * 8
        # Add 2 transfers with 2 fragments each (incomplete)
        for i in range(2):
            h0 = FragmentHeader(fragment_id=_fid(i), fragment_index=0, total_fragments=2, message_type=2)
            buf.append(sender, h0, b"first_")
        # Third transfer should be rejected
        h = FragmentHeader(fragment_id=_fid(99), fragment_index=0, total_fragments=1, message_type=2)
        result = buf.append(sender, h, b"rejected")
        assert result is None

    def test_parse_fragment_payload(self) -> None:
        """parse_fragment_payload が正しくパースできる."""
        fid = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        payload = fid + (0).to_bytes(2, "big") + (3).to_bytes(2, "big") + bytes([5]) + b"data"
        parsed = parse_fragment_payload(payload)
        assert parsed is not None
        assert parsed[0] == fid
        assert parsed[1] == 0
        assert parsed[2] == 3
        assert parsed[3] == 5
        assert parsed[4] == b"data"

    def test_parse_fragment_payload_too_short(self) -> None:
        """短すぎるペイロードは None を返す."""
        assert parse_fragment_payload(b"too") is None

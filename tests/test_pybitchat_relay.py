"""Phase 4 TDD: メッセージルーティング（フラッディングリレー + 重複排除）."""

from __future__ import annotations

import time


class TestMessageDeduplicator:
    """メッセージ重複排除（タイムウィンドウ付き）."""

    def test_first_seen_is_not_duplicate(self) -> None:
        """初見のメッセージは重複と判定されない."""
        from uagent.tools.pybitchat_shared import MessageDeduplicator

        dd = MessageDeduplicator(window_seconds=10.0)
        msg_id = "msg001"
        assert dd.is_duplicate(msg_id) is False

    def test_same_id_within_window_is_duplicate(self) -> None:
        """同一メッセージIDをウィンドウ内で再度確認すると重複と判定."""
        from uagent.tools.pybitchat_shared import MessageDeduplicator

        dd = MessageDeduplicator(window_seconds=10.0)
        msg_id = "msg001"
        dd.is_duplicate(msg_id)  # first: not duplicate, records it
        assert dd.is_duplicate(msg_id) is True

    def test_after_window_expiry_not_duplicate(self) -> None:
        """ウィンドウ経過後は重複と判定されない."""
        from uagent.tools.pybitchat_shared import MessageDeduplicator

        dd = MessageDeduplicator(window_seconds=0.1)
        msg_id = "msg001"
        dd.is_duplicate(msg_id)  # record
        time.sleep(0.15)
        assert dd.is_duplicate(msg_id) is False  # expired, seen again as new

    def test_multiple_messages(self) -> None:
        """複数メッセージを個別に管理."""
        from uagent.tools.pybitchat_shared import MessageDeduplicator

        dd = MessageDeduplicator(window_seconds=10.0)
        assert dd.is_duplicate("msg1") is False
        assert dd.is_duplicate("msg2") is False
        assert dd.is_duplicate("msg1") is True  # duplicate
        assert dd.is_duplicate("msg2") is True  # duplicate
        assert dd.is_duplicate("msg3") is False  # new

    def test_cleanup_expired(self) -> None:
        """期限切れエントリをクリーンアップ."""
        from uagent.tools.pybitchat_shared import MessageDeduplicator

        dd = MessageDeduplicator(window_seconds=0.1)
        dd.is_duplicate("msg1")
        dd.is_duplicate("msg2")
        assert dd.count() == 2
        time.sleep(0.15)
        dd.cleanup()
        assert dd.count() == 0


class TestRelayController:
    """リレー制御（遅延 + 確率的抑制）."""

    def test_relay_enabled_by_default(self) -> None:
        """デフォルトではリレーが有効."""
        from uagent.tools.pybitchat_shared import RelayController

        rc = RelayController()
        assert isinstance(rc.should_relay(), bool)

    def test_relay_probability_zero_disables(self) -> None:
        """確率0ではリレーしない."""
        from uagent.tools.pybitchat_shared import RelayController

        rc = RelayController(base_probability=0.0)
        results = [rc.should_relay() for _ in range(100)]
        assert any(results) is False

    def test_relay_probability_one_always(self) -> None:
        """確率1では常にリレー."""
        from uagent.tools.pybitchat_shared import RelayController

        rc = RelayController(base_probability=1.0)
        results = [rc.should_relay() for _ in range(100)]
        assert all(results) is True

    def test_relay_delay_within_range(self) -> None:
        """リレー遅延が指定範囲内."""
        from uagent.tools.pybitchat_shared import RelayController

        rc = RelayController(min_delay_ms=100.0, max_delay_ms=500.0)
        delays = [rc.get_delay() for _ in range(50)]
        assert all(100.0 <= d <= 500.0 for d in delays)

    def test_high_degree_reduces_probability(self) -> None:
        """高次数ノードでは抑制確率が上がる."""
        from uagent.tools.pybitchat_shared import RelayController

        rc = RelayController(base_probability=1.0, degree_threshold=3)
        # Low degree: should relay
        assert rc.should_relay(degree=1) is True
        # High degree: may suppress
        results = [rc.should_relay(degree=10) for _ in range(50)]
        # With high degree, some should be suppressed
        assert any(r is False for r in results)

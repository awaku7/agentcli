"""Phase 6 TDD: Courier / Store-and-Forward."""

from __future__ import annotations

from uagent.tools.pybitchat_shared import CourierEnvelope, CourierStore


class TestCourierEnvelope:
    """CourierEnvelope のユニットテスト."""

    def test_create_envelope(self) -> None:
        """エンベロープを作成できる."""
        env = CourierEnvelope(
            recipient_id="peer1",
            sender_id="peer2",
            payload=b"Hello offline peer!",
        )
        assert env.recipient_id == "peer1"
        assert env.sender_id == "peer2"
        assert env.payload == b"Hello offline peer!"
        assert env.envelope_id is not None

    def test_envelope_to_dict(self) -> None:
        """to_dict() で辞書に変換できる."""
        env = CourierEnvelope(
            recipient_id="peer1",
            sender_id="peer2",
            payload=b"test",
            envelope_id="test-id-123",
        )
        d = env.to_dict()
        assert d["envelope_id"] == "test-id-123"
        assert d["recipient_id"] == "peer1"
        assert d["sender_id"] == "peer2"
        assert d["payload_hex"] == b"test".hex()


class TestCourierStore:
    """CourierStore のユニットテスト."""

    def test_store_and_retrieve(self) -> None:
        """エンベロープを保存して取得できる."""
        store = CourierStore()
        env = CourierEnvelope(
            recipient_id="peer1",
            sender_id="peer2",
            payload=b"Hello offline peer!",
        )
        store.store(env)
        results = store.retrieve("peer1")
        assert len(results) == 1
        assert results[0].sender_id == "peer2"
        assert results[0].payload == b"Hello offline peer!"

    def test_store_for_unknown_recipient(self) -> None:
        """存在しない受信者には何も返さない."""
        store = CourierStore()
        env = CourierEnvelope(recipient_id="alice", sender_id="bob", payload=b"hi")
        store.store(env)
        results = store.retrieve("charlie")
        assert len(results) == 0

    def test_multiple_envelopes_for_same_recipient(self) -> None:
        """同一受信者に複数エンベロープ."""
        store = CourierStore()
        for i in range(3):
            env = CourierEnvelope(
                recipient_id="peer1",
                sender_id="sender{}".format(i),
                payload=f"msg{i}".encode(),
            )
            store.store(env)
        results = store.retrieve("peer1")
        assert len(results) == 3

    def test_retrieve_removes_envelopes(self) -> None:
        """retrieve 後もエンベロープは削除されない（配送確認後 remove する）."""
        store = CourierStore()
        env = CourierEnvelope(
            recipient_id="peer1", sender_id="peer2", payload=b"persist"
        )
        store.store(env)
        results1 = store.retrieve("peer1")
        assert len(results1) == 1
        results2 = store.retrieve("peer1")
        assert len(results2) == 1

    def test_envelope_expiry(self) -> None:
        """期限切れエンベロープは取得されない."""
        store = CourierStore()

        # Past expiry
        env = CourierEnvelope(
            recipient_id="peer1",
            sender_id="peer2",
            payload=b"expired",
            created_at=0.0,
            ttl_seconds=1.0,
        )
        store.store(env)
        results = store.retrieve("peer1")
        assert len(results) == 0

        # Valid envelope
        env2 = CourierEnvelope(
            recipient_id="peer1",
            sender_id="peer3",
            payload=b"fresh",
            ttl_seconds=3600.0,
        )
        store.store(env2)
        results = store.retrieve("peer1")
        assert len(results) == 1
        assert results[0].sender_id == "peer3"

    def test_pending_count(self) -> None:
        """pending_count() が正しい数を返す."""
        store = CourierStore()
        assert store.count() == 0
        env = CourierEnvelope(
            recipient_id="peer1", sender_id="peer2", payload=b"count_test"
        )
        store.store(env)
        assert store.count() == 1

        # Expired should not count
        env2 = CourierEnvelope(
            recipient_id="peer2",
            sender_id="peer1",
            payload=b"old",
            created_at=0.0,
            ttl_seconds=1.0,
        )
        store.store(env2)
        assert store.count() == 1

"""Replay/freshness guard tests for the experimental Nostr remote path."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from uagent.nostr_remote_state import SQLiteReplayStore, validate_rumor_timestamp


def _hex32(value: int) -> str:
    return value.to_bytes(32, "big").hex()


def test_rumor_timestamp_boundaries_use_inner_timestamp() -> None:
    now = 1_700_000_000
    validate_rumor_timestamp(now - 600, now=now)
    validate_rumor_timestamp(now + 300, now=now)

    with pytest.raises(ValueError, match="too old"):
        validate_rumor_timestamp(now - 601, now=now)
    with pytest.raises(ValueError, match="future"):
        validate_rumor_timestamp(now + 301, now=now)
    with pytest.raises(ValueError):
        validate_rumor_timestamp(True, now=now)


def test_replay_store_is_atomic_and_survives_reopen(tmp_path) -> None:
    path = tmp_path / "remote-replay.sqlite3"
    sender = _hex32(1)
    rumor = _hex32(2)

    with SQLiteReplayStore(path) as store:
        assert store.claim(sender, rumor, received_at=100)
        assert not store.claim(sender, rumor, received_at=101)
        assert store.claim(sender, _hex32(3), received_at=102)

    with SQLiteReplayStore(path) as reopened:
        assert not reopened.claim(sender, rumor, received_at=103)
        assert reopened.claim(_hex32(4), rumor, received_at=104)


def test_replay_store_concurrent_claim_has_single_winner(tmp_path) -> None:
    path = tmp_path / "remote-replay-concurrent.sqlite3"
    sender = _hex32(1)
    rumor = _hex32(2)
    store = SQLiteReplayStore(path)
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda received: store.claim(sender, rumor, received_at=received),
                    range(8),
                )
            )
        assert results.count(True) == 1
        assert results.count(False) == 7
    finally:
        store.close()


def test_replay_store_rejects_malformed_ids_and_time(tmp_path) -> None:
    with SQLiteReplayStore(tmp_path / "remote-replay-invalid.sqlite3") as store:
        with pytest.raises(ValueError):
            store.claim("not-a-key", _hex32(2))
        with pytest.raises(ValueError):
            store.claim(_hex32(1), _hex32(2), received_at=-1)

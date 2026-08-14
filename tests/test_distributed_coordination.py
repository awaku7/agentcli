from uagent.runtime.distributed_coordination import LeaderLease


def test_leader_lease_acquire_renew_release(tmp_path) -> None:
    path = tmp_path / "leader.json"
    first = LeaderLease(path, owner="first", ttl=10)
    second = LeaderLease(path, owner="second", ttl=10)
    assert first.acquire() is True
    assert second.acquire() is False
    assert first.renew() is True
    assert second.release() is False
    assert first.release() is True
    assert second.acquire() is True

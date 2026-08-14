# Distributed Coordination

`uagent.runtime.distributed_coordination.LeaderLease` provides a small single-leader lease for runtimes sharing a filesystem.

```python
lease = LeaderLease("/shared/uagent/leader.json", ttl=30)
if lease.acquire():
    try:
        run_scheduler_cycle()
        lease.renew()
    finally:
        lease.release()
```

Only the owner can renew or release the lease. Expired leases can be taken over. This primitive is intentionally conservative and is not a replacement for a production consensus system such as etcd or ZooKeeper.

Lease state, owner IDs, and error types are machine-readable and are not localized. User-facing messages should be translated at the CLI/Web/GUI boundary.

from __future__ import annotations

import json
import threading
import time
from contextvars import ContextVar

from uagent.runtime.sub_agent_jobs import (
    CURRENT_SUB_AGENT_JOB_ID,
    CURRENT_SUB_AGENT_JOB_MODE,
    SubAgentJobManager,
    SubAgentJobOwner,
    SubAgentJobSettings,
)


def _owner(session: str = "session-1") -> SubAgentJobOwner:
    return SubAgentJobOwner(entry_point="cli", session_id=session)


def _manager(**overrides) -> SubAgentJobManager:
    values = {
        "workers": 1,
        "queue_limit": 4,
        "owner_limit": 8,
        "completed_limit": 10,
        "result_ttl_sec": 60,
        "event_limit": 20,
        "log_max_bytes": 4096,
        "result_max_bytes": 4096,
        "shutdown_timeout_sec": 0.2,
    }
    values.update(overrides)
    return SubAgentJobManager(SubAgentJobSettings(**values))


def test_spawn_returns_before_worker_finishes_and_context_is_propagated():
    manager = _manager()
    started = threading.Event()
    release = threading.Event()
    marker = CURRENT_SUB_AGENT_JOB_ID.set("parent-job")
    inherited = ContextVar("test_inherited_context", default=None)
    inherited_marker = inherited.set("spawn-snapshot")
    try:

        def worker(_ctx):
            started.set()
            assert release.wait(2)
            return json.dumps(
                {
                    "id": CURRENT_SUB_AGENT_JOB_ID.get(),
                    "mode": CURRENT_SUB_AGENT_JOB_MODE.get(),
                    "inherited": inherited.get(),
                }
            )

        t0 = time.monotonic()
        accepted = manager.spawn(
            owner=_owner(), agent_name="planner", task="research", worker=worker
        )
        assert time.monotonic() - t0 < 0.5
        assert accepted["status"] == "accepted"
        job_id = accepted["job_id"]
        assert started.wait(1)
        assert manager.get(owner=_owner(), job_id=job_id)["state"] == "running"
        release.set()
        result = manager.wait(owner=_owner(), job_id=job_id, timeout=2)
        assert result["state"] == "completed"
        assert json.loads(result["result"]) == {
            "id": job_id,
            "mode": "background",
            "inherited": "spawn-snapshot",
        }
        assert CURRENT_SUB_AGENT_JOB_ID.get() == "parent-job"
    finally:
        inherited.reset(inherited_marker)
        CURRENT_SUB_AGENT_JOB_ID.reset(marker)
        release.set()
        manager.shutdown()


def test_job_root_is_captured_at_spawn_and_does_not_follow_main_cwd(
    tmp_path, monkeypatch
):
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    monkeypatch.chdir(project_a)
    manager = _manager()
    started = threading.Event()
    release = threading.Event()
    try:

        def worker(ctx):
            started.set()
            assert release.wait(2)
            from uagent.runtime.sub_agent_jobs import current_sub_agent_job_root

            return json.dumps(
                {
                    "context_root": str(ctx.job_root),
                    "current_root": str(current_sub_agent_job_root()),
                }
            )

        accepted = manager.spawn(
            owner=_owner(), agent_name="worker", task="root", worker=worker
        )
        assert started.wait(1)
        monkeypatch.chdir(project_b)
        release.set()
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        output = json.loads(result["result"])
        expected = str(project_a.resolve())
        assert output == {"context_root": expected, "current_root": expected}
    finally:
        release.set()
        manager.shutdown()


def test_queue_is_bounded_and_queued_cancel_releases_capacity():
    manager = _manager(queue_limit=1)
    started = threading.Event()
    release = threading.Event()
    try:
        first = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="first",
            worker=lambda _ctx: (started.set(), release.wait(2), "done")[-1],
        )
        assert started.wait(1)
        second = manager.spawn(
            owner=_owner(), agent_name="worker", task="second", worker=lambda _ctx: "ok"
        )
        rejected = manager.spawn(
            owner=_owner(), agent_name="worker", task="third", worker=lambda _ctx: "ok"
        )
        assert second["status"] == "accepted"
        assert rejected == {"status": "rejected", "reason": "queue_full"}
        cancelled = manager.cancel(owner=_owner(), job_id=second["job_id"])
        assert cancelled["state"] == "cancelled"
        third = manager.spawn(
            owner=_owner(), agent_name="worker", task="third", worker=lambda _ctx: "ok"
        )
        assert third["status"] == "accepted"
        release.set()
        assert (
            manager.wait(owner=_owner(), job_id=first["job_id"], timeout=2)["state"]
            == "completed"
        )
        assert (
            manager.wait(owner=_owner(), job_id=third["job_id"], timeout=2)["state"]
            == "completed"
        )
    finally:
        release.set()
        manager.shutdown()


def test_owner_limit_and_cross_owner_access_are_isolated():
    manager = _manager(owner_limit=1)
    started = threading.Event()
    release = threading.Event()
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="hold",
            worker=lambda _ctx: (started.set(), release.wait(2), "done")[-1],
        )
        assert started.wait(1)
        over_limit = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="another",
            worker=lambda _ctx: "ok",
        )
        assert over_limit == {"status": "rejected", "reason": "owner_limit"}
        assert manager.get(owner=_owner("session-2"), job_id=accepted["job_id"]) == {
            "status": "error",
            "reason": "not_found",
        }
        assert manager.cancel(owner=_owner("session-2"), job_id=accepted["job_id"]) == {
            "status": "error",
            "reason": "not_found",
        }
    finally:
        release.set()
        manager.shutdown()


def test_absolute_deadline_expires_queued_job_without_starting_worker():
    manager = _manager(queue_limit=2)
    started = threading.Event()
    release = threading.Event()
    try:
        blocker = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="block",
            worker=lambda _ctx: (started.set(), release.wait(2), "done")[-1],
        )
        assert started.wait(1)
        queued = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="expires",
            worker=lambda _ctx: (_ for _ in ()).throw(AssertionError("must not run")),
            timeout=0.08,
        )
        result = manager.wait(owner=_owner(), job_id=queued["job_id"], timeout=1)
        assert result["state"] == "timed_out"
        assert result["started_at"] is None
        replacement = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="replacement",
            worker=lambda _ctx: "ok",
        )
        assert replacement["status"] == "accepted"
        release.set()
        assert (
            manager.wait(owner=_owner(), job_id=blocker["job_id"], timeout=2)["state"]
            == "completed"
        )
        assert (
            manager.wait(owner=_owner(), job_id=replacement["job_id"], timeout=2)[
                "state"
            ]
            == "completed"
        )
    finally:
        release.set()
        manager.shutdown()


def test_deadline_context_and_cooperative_cancel():
    manager = _manager()
    observed = threading.Event()
    try:

        def worker(ctx):
            assert ctx.remaining is not None
            ctx.raise_if_cancelled()
            observed.set()
            return "done"

        accepted = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="deadline",
            worker=worker,
            timeout=1,
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert observed.is_set()
        assert result["state"] == "completed"

        started = threading.Event()
        canceled = threading.Event()

        def cancellable(ctx):
            started.set()
            while not ctx.cancel_event.wait(0.01):
                pass
            try:
                ctx.raise_if_cancelled()
            except Exception:
                canceled.set()
                raise

        second = manager.spawn(
            owner=_owner(), agent_name="worker", task="cancel", worker=cancellable
        )
        assert started.wait(1)
        assert (
            manager.cancel(owner=_owner(), job_id=second["job_id"])["state"]
            == "cancelled"
        )
        assert canceled.wait(1)
    finally:
        manager.shutdown()


def test_running_job_deadline_cancels_cooperatively():
    manager = _manager()
    started = threading.Event()
    cancellation_seen = threading.Event()
    try:

        def worker(ctx):
            started.set()
            try:
                while not ctx.cancel_event.wait(0.01):
                    ctx.raise_if_cancelled()
            except Exception:
                cancellation_seen.set()
                raise
            ctx.raise_if_cancelled()

        accepted = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="running deadline",
            worker=worker,
            timeout=0.08,
        )
        assert started.wait(1)
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=1)
        assert result["state"] == "timed_out"
        assert cancellation_seen.wait(1)
    finally:
        manager.shutdown()


def test_result_and_event_buffers_are_bounded_and_report_truncation():
    manager = _manager(result_max_bytes=24, log_max_bytes=32, event_limit=2)
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="large",
            worker=lambda _ctx: "x" * 100,
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        assert result["truncated"] is True
        assert len(result["result"].encode("utf-8")) <= 24
        events = manager.get_events(owner=_owner(), job_id=accepted["job_id"])
        assert len(events["events"]) <= 2
        assert events["truncated"] is True
    finally:
        manager.shutdown()


def test_shutdown_is_bounded_for_noncooperative_worker():
    manager = _manager(shutdown_timeout_sec=0.05)
    started = threading.Event()
    release = threading.Event()
    accepted = manager.spawn(
        owner=_owner(),
        agent_name="worker",
        task="stuck",
        worker=lambda _ctx: (started.set(), release.wait(1), "late")[-1],
    )
    assert started.wait(1)
    t0 = time.monotonic()
    lingering = manager.shutdown(timeout=0.05)
    assert time.monotonic() - t0 < 0.5
    assert accepted["job_id"] in lingering
    assert manager.get(owner=_owner(), job_id=accepted["job_id"])[
        "orphaned_on_shutdown"
    ]
    release.set()


def test_completed_results_are_evicted_by_ttl_and_limit():
    manager = _manager(completed_limit=1)
    try:
        first = manager.spawn(
            owner=_owner(), agent_name="worker", task="one", worker=lambda _ctx: "one"
        )
        assert (
            manager.wait(owner=_owner(), job_id=first["job_id"], timeout=2)["state"]
            == "completed"
        )
        second = manager.spawn(
            owner=_owner(), agent_name="worker", task="two", worker=lambda _ctx: "two"
        )
        assert (
            manager.wait(owner=_owner(), job_id=second["job_id"], timeout=2)["state"]
            == "completed"
        )
        assert manager.get(owner=_owner(), job_id=first["job_id"]) == {
            "status": "error",
            "reason": "not_found",
        }
        assert manager.get(owner=_owner(), job_id=second["job_id"])["result"] == "two"
    finally:
        manager.shutdown()


def test_oversized_task_is_rejected_before_queue_admission():
    manager = _manager(task_max_bytes=8)
    try:
        result = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="123456789",
            worker=lambda _ctx: "ok",
        )
        assert result == {"status": "rejected", "reason": "task_too_large"}
        assert manager.running_count(owner=_owner()) == 0
    finally:
        manager.shutdown()


def test_completed_results_expire_by_ttl():
    manager = _manager(result_ttl_sec=0.05)
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="short-lived",
            worker=lambda _ctx: "ok",
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        time.sleep(0.08)
        assert manager.get(owner=_owner(), job_id=accepted["job_id"]) == {
            "status": "error",
            "reason": "not_found",
        }
    finally:
        manager.shutdown()


def test_worker_status_is_normalized_and_secrets_are_masked():
    manager = _manager()
    try:
        blocked = manager.spawn(
            owner=_owner(),
            agent_name="reviewer",
            task="review",
            worker=lambda _ctx: json.dumps(
                {"status": "blocked", "message": "needs approval"}
            ),
        )
        blocked_result = manager.wait(
            owner=_owner(), job_id=blocked["job_id"], timeout=2
        )
        assert blocked_result["state"] == "blocked"

        secret = manager.spawn(
            owner=_owner(),
            agent_name="worker",
            task="secret result",
            worker=lambda _ctx: '{"api_key":"super-secret-value"}',
        )
        secret_result = manager.wait(owner=_owner(), job_id=secret["job_id"], timeout=2)
        assert "super-secret-value" not in secret_result["result"]
        assert "********" in secret_result["result"]
    finally:
        manager.shutdown()

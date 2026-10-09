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
    notice_callback = overrides.pop("notice_callback", None)
    handoff_dispatch_policy = overrides.pop("handoff_dispatch_policy", None)
    values.update(overrides)
    return SubAgentJobManager(
        SubAgentJobSettings(**values),
        notice_callback=notice_callback,
        handoff_dispatch_policy=handoff_dispatch_policy,
    )


def _dispatch(owner: SubAgentJobOwner, task: str):
    from uagent.runtime.handoff_projection import HandoffBounds
    from uagent.runtime.sub_agent_handoff import SubAgentDispatch

    return SubAgentDispatch(
        dispatch_id="dispatch-test",
        source_session_id="child-session",
        objective=task,
        bounds=HandoffBounds(owner.session_id, 0),
        _context_json='{"kind":"main_to_subagent"}',
        _source_refs=(),
        _source_access_check=lambda _ref: False,
        _store=object(),
    )


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


def test_structured_job_carries_host_dispatch_and_rejects_live_messages():
    owner = _owner()
    started = threading.Event()
    release = threading.Event()
    dispatch = _dispatch(owner, "inspect the current regression")
    captured = []
    manager = _manager(
        handoff_dispatch_policy=lambda actual_owner, agent, task: (
            captured.append((actual_owner, agent, task)) or dispatch
        )
    )
    try:
        assert manager.structured_handoff_enabled

        def worker(context):
            assert context.handoff_dispatch is dispatch
            started.set()
            assert release.wait(2)
            return "indexed child result"

        accepted = manager.spawn(
            owner=owner,
            agent_name="planner",
            task=dispatch.objective,
            worker=worker,
        )
        assert accepted["status"] == "accepted"
        assert started.wait(1)
        assert captured == [(owner, "planner", dispatch.objective)]
        assert manager.send_message(
            owner=owner, job_id=accepted["job_id"], message="new instruction"
        ) == {
            "status": "rejected",
            "reason": "structured_handoff_requires_new_dispatch",
        }
        release.set()
        result = manager.wait(owner=owner, job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        assert result["result"] == "indexed child result"
    finally:
        release.set()
        manager.shutdown()


def test_structured_job_does_not_capture_when_shared_store_is_requested():
    owner = _owner()
    calls = []
    manager = _manager(handoff_dispatch_policy=lambda *_args: calls.append(True))
    try:
        rejected = manager.spawn(
            owner=owner,
            agent_name="planner",
            task="task",
            worker=lambda _context: "unused",
            store_key="result",
        )
        assert rejected == {
            "status": "rejected",
            "reason": "structured_handoff_shared_store_disabled",
        }
        assert calls == []
    finally:
        manager.shutdown()


def test_structured_job_rejects_a_dispatch_for_another_owner():
    owner = _owner()
    other_owner = SubAgentJobOwner(entry_point="cli", session_id="other-session")
    manager = _manager(
        handoff_dispatch_policy=lambda _owner, _agent, task: _dispatch(
            other_owner, task
        )
    )
    try:
        rejected = manager.spawn(
            owner=owner,
            agent_name="planner",
            task="task",
            worker=lambda _context: "unused",
        )
        assert rejected == {
            "status": "rejected",
            "reason": "structured_handoff_scope_mismatch",
        }
    finally:
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


def test_job_log_sink_and_lifecycle_notices_are_bounded_and_private():
    notices = []
    manager = _manager(notice_callback=notices.append)
    try:

        def worker(ctx):
            ctx.log("tool_trace", '{"api_key":"hidden-key"}')
            return "done"

        accepted = manager.spawn(
            owner=_owner(), agent_name="worker", task="logging", worker=worker
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        events = manager.get_events(owner=_owner(), job_id=accepted["job_id"])["events"]
        logged = next(event for event in events if event["kind"] == "tool_trace")
        assert "hidden-key" not in logged["message"]
        assert {event["event"] for event in notices} == {"started", "finished"}
        assert all(event["job_id"] == accepted["job_id"] for event in notices)
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


def test_accepted_inbox_message_is_delivered_before_job_completion():
    manager = _manager()
    first_started = threading.Event()
    release_first = threading.Event()
    calls = []
    try:

        def worker(ctx):
            calls.append(ctx.job_id)
            if len(calls) == 1:
                first_started.set()
                assert release_first.wait(2)
                return "initial-result"
            messages = ctx.drain_messages()
            return json.dumps({"delivered": messages})

        accepted = manager.spawn(
            owner=_owner(), agent_name="planner", task="work", worker=worker
        )
        assert first_started.wait(1)
        delivered = manager.send_message(
            owner=_owner(), job_id=accepted["job_id"], message="Use evidence B"
        )
        assert delivered["status"] == "accepted"
        release_first.set()
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        assert len(calls) == 2
        assert json.loads(result["result"])["delivered"] == [
            {"sequence": delivered["sequence"], "message": "Use evidence B"}
        ]
        assert manager.send_message(
            owner=_owner(), job_id=accepted["job_id"], message="too late"
        ) == {"status": "rejected", "reason": "job_not_running"}
    finally:
        release_first.set()
        manager.shutdown()


def test_store_key_is_published_only_after_success_and_is_owner_scoped():
    manager = _manager()
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="planner",
            task="publish",
            worker=lambda _ctx: "approved output",
            store_key="plan",
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        assert manager.load_shared_results(owner=_owner(), keys=["plan"]) == (
            {"plan": "approved output"},
            [],
        )
        assert manager.load_shared_results(
            owner=_owner("session-2"), keys=["plan"]
        ) == (
            {},
            ["plan"],
        )
    finally:
        manager.shutdown()


def test_shared_store_key_is_reserved_until_completion_and_conflicts():
    manager = _manager()
    try:
        started = threading.Event()
        release = threading.Event()
        first = manager.spawn(
            owner=_owner(),
            agent_name="planner",
            task="reserve",
            worker=lambda _ctx: (started.set(), release.wait(2), "done")[-1],
            store_key="same-key",
        )
        assert started.wait(1)
        duplicate = manager.spawn(
            owner=_owner(),
            agent_name="reviewer",
            task="duplicate key",
            worker=lambda _ctx: "unused",
            store_key="same-key",
        )
        assert duplicate == {"status": "rejected", "reason": "store_key_conflict"}
        release.set()
        assert (
            manager.wait(owner=_owner(), job_id=first["job_id"], timeout=2)["state"]
            == "completed"
        )
        assert manager.load_shared_results(owner=_owner(), keys=["same-key"])[0] == {
            "same-key": "done"
        }
    finally:
        release.set()
        manager.shutdown()


def test_job_message_inbox_has_a_total_byte_limit():
    manager = _manager(inbox_limit=10, inbox_max_bytes=8, message_max_bytes=8)
    started = threading.Event()
    release = threading.Event()
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="planner",
            task="work",
            worker=lambda _ctx: (started.set(), release.wait(2), "done")[-1],
        )
        assert started.wait(1)
        assert (
            manager.send_message(
                owner=_owner(), job_id=accepted["job_id"], message="123456"
            )["status"]
            == "accepted"
        )
        assert manager.send_message(
            owner=_owner(), job_id=accepted["job_id"], message="789"
        ) == {"status": "rejected", "reason": "inbox_full"}
        release.set()
        assert (
            manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)["state"]
            == "completed"
        )
    finally:
        release.set()
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


def test_failed_store_job_releases_reservation_without_publishing():
    manager = _manager()
    try:
        failed = manager.spawn(
            owner=_owner(),
            agent_name="planner",
            task="fail",
            worker=lambda _ctx: (_ for _ in ()).throw(RuntimeError("failure")),
            store_key="retry-key",
        )
        failed_result = manager.wait(owner=_owner(), job_id=failed["job_id"], timeout=2)
        assert failed_result["state"] == "failed"
        assert manager.load_shared_results(owner=_owner(), keys=["retry-key"]) == (
            {},
            ["retry-key"],
        )
        retry = manager.spawn(
            owner=_owner(),
            agent_name="planner",
            task="retry",
            worker=lambda _ctx: "approved",
            store_key="retry-key",
        )
        assert retry["status"] == "accepted"
        assert (
            manager.wait(owner=_owner(), job_id=retry["job_id"], timeout=2)["state"]
            == "completed"
        )
    finally:
        manager.shutdown()


def test_subagent_provider_timeout_is_clamped_to_job_deadline():
    from uagent.tools.sub_agent_tool import SubAgentRunner

    manager = _manager()
    try:
        accepted = manager.spawn(
            owner=_owner(),
            agent_name="planner",
            task="deadline clamp",
            timeout=0.5,
            worker=lambda _ctx: str(SubAgentRunner._job_call_timeout(60)),
        )
        result = manager.wait(owner=_owner(), job_id=accepted["job_id"], timeout=2)
        assert result["state"] == "completed"
        assert 0 < float(result["result"]) <= 0.5
    finally:
        manager.shutdown()

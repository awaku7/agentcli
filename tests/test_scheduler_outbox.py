from __future__ import annotations

import queue
import time
from datetime import timedelta

from uagent.scheduler import (
    SCHEDULE_TYPE_ONCE,
    ScheduleItem,
    SchedulerRunStore,
    SchedulerService,
    SchedulerStore,
    format_iso_datetime,
    utc_now,
)


class _FailingSink:
    def __init__(self) -> None:
        self.attempts = 0

    def put(self, _payload) -> None:
        self.attempts += 1
        raise OSError("sink unavailable")


def _add_due_schedule(store: SchedulerStore, schedule_id: str, owner: str) -> None:
    store.add_item(
        ScheduleItem(
            id=schedule_id,
            type=SCHEDULE_TYPE_ONCE,
            at=format_iso_datetime(utc_now() - timedelta(seconds=1)),
            message="",
            llm_prompt="recover this scheduled run",
            owner_instance_id=owner,
        )
    )


def test_sink_failure_keeps_event_pending_until_redelivery(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    _add_due_schedule(schedules, "outbox-1", "instance-a")

    failing = _FailingSink()
    service = SchedulerService(
        failing,
        store=schedules,
        run_store=runs,
        instance_id="instance-a",
        poll_interval_s=0.1,
    )
    service._fire_due_items()

    assert failing.attempts == 1
    assert schedules.get_item("outbox-1") is None
    pending = schedules.list_events("pending")
    assert len(pending) == 1
    assert pending[0]["payload"]["kind"] == "user"
    assert pending[0]["attempt_count"] == 1
    assert "sink unavailable" in pending[0]["last_error"]
    run = runs.get(pending[0]["run_id"])
    assert run is not None
    assert run.status == "queued"

    time.sleep(0.12)
    events = queue.Queue()
    recovered = SchedulerService(
        events,
        store=schedules,
        run_store=runs,
        instance_id="instance-a",
        poll_interval_s=0.1,
    )
    recovered._fire_due_items()

    event = events.get_nowait()
    assert event["run_id"] == run.run_id
    assert event["schedule_id"] == "outbox-1"
    assert schedules.list_events("pending") == []
    delivered = schedules.list_events("delivered")
    assert len(delivered) == 1
    assert delivered[0]["run_id"] == run.run_id

    recovered._fire_due_items()
    assert events.empty()


def test_pending_event_is_not_dispatched_to_foreign_instance(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    _add_due_schedule(schedules, "outbox-2", "instance-a")

    SchedulerService(
        _FailingSink(),
        store=schedules,
        run_store=runs,
        instance_id="instance-a",
        poll_interval_s=0.1,
    )._fire_due_items()

    foreign_events = queue.Queue()
    foreign = SchedulerService(
        foreign_events,
        store=schedules,
        run_store=runs,
        instance_id="instance-b",
        poll_interval_s=0.1,
    )
    foreign._fire_due_items()

    assert foreign_events.empty()
    pending = schedules.list_events("pending")
    assert len(pending) == 1
    assert pending[0]["target_instance_id"] == "instance-a"


def test_explicit_orphan_reclaim_allows_redelivery_after_owner_restart(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    _add_due_schedule(schedules, "outbox-3", "instance-a")

    SchedulerService(
        _FailingSink(),
        store=schedules,
        run_store=runs,
        instance_id="instance-a",
        poll_interval_s=0.1,
    )._fire_due_items()

    assert schedules.reclaim_orphaned_events("instance-a", "instance-b") == 1

    events = queue.Queue()
    SchedulerService(
        events,
        store=schedules,
        run_store=runs,
        instance_id="instance-b",
        poll_interval_s=0.1,
    )._fire_due_items()

    event = events.get_nowait()
    assert event["schedule_id"] == "outbox-3"
    assert schedules.list_events("pending") == []
    delivered = schedules.list_events("delivered")
    assert len(delivered) == 1
    assert delivered[0]["target_instance_id"] == "instance-b"

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


class _FailFirstSink:
    def __init__(self) -> None:
        self.calls = []

    def put(self, payload) -> None:
        self.calls.append(dict(payload))
        if len(self.calls) == 1:
            raise OSError("first event rejected")


def _add_due_schedule(
    store: SchedulerStore,
    schedule_id: str,
    owner: str,
    *,
    message: str = "",
    prompt: str = "recover this scheduled run",
) -> None:
    store.add_item(
        ScheduleItem(
            id=schedule_id,
            type=SCHEDULE_TYPE_ONCE,
            at=format_iso_datetime(utc_now() - timedelta(seconds=1)),
            message=message,
            llm_prompt=prompt,
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

    assert len(schedules.list_events("pending")) == 1
    event = events.get_nowait()
    assert event["run_id"] == run.run_id
    assert event["schedule_id"] == "outbox-1"
    assert schedules.list_events("pending") == []
    delivered = schedules.list_events("delivered")
    assert len(delivered) == 1
    assert delivered[0]["run_id"] == run.run_id

    recovered._fire_due_items()
    assert events.empty()


def test_failed_notice_does_not_allow_execution_event_to_overtake_it(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    _add_due_schedule(
        schedules,
        "outbox-order",
        "instance-a",
        message="timer finished",
        prompt="run after notice",
    )

    sink = _FailFirstSink()
    service = SchedulerService(
        sink,
        store=schedules,
        run_store=runs,
        instance_id="instance-a",
        poll_interval_s=0.1,
    )
    service._fire_due_items()
    service._fire_due_items()

    assert [event["kind"] for event in sink.calls] == ["schedule_notice"]
    pending = schedules.list_events("pending")
    assert [event["payload"]["kind"] for event in pending] == [
        "schedule_notice",
        "user",
    ]


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

    reclaimed = schedules.reclaim_orphaned_instance("instance-a", "instance-b")
    assert reclaimed == {"schedules": 0, "events": 1}

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
    assert event["owner_instance_id"] == "instance-b"
    assert event["reclaimed_from_instance_id"] == "instance-a"
    assert schedules.list_events("pending") == []
    delivered = schedules.list_events("delivered")
    assert len(delivered) == 1
    assert delivered[0]["target_instance_id"] == "instance-b"


def test_explicit_orphan_reclaim_recovers_schedule_before_outbox_creation(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    _add_due_schedule(schedules, "outbox-pre-finalize", "instance-a")

    due = schedules.claim_due_items("instance-a", utc_now())
    assert len(due) == 1

    reclaimed = schedules.reclaim_orphaned_instance("instance-a", "instance-b")
    assert reclaimed == {"schedules": 1, "events": 0}

    events = queue.Queue()
    SchedulerService(
        events,
        store=schedules,
        run_store=runs,
        instance_id="instance-b",
        poll_interval_s=0.1,
    )._fire_due_items()

    event = events.get_nowait()
    assert event["schedule_id"] == "outbox-pre-finalize"
    assert event["owner_instance_id"] == "instance-b"
    assert schedules.get_item("outbox-pre-finalize") is None


def test_reclaim_after_run_creation_reuses_same_idempotent_run(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    _add_due_schedule(schedules, "outbox-run-created", "instance-a")

    due = schedules.claim_due_items("instance-a", utc_now())
    assert len(due) == 1
    item, due_at = due[0]
    original_run = runs.create(
        item.id,
        idempotency_key=f"{item.id}:{due_at}",
        metadata={"llm_prompt": item.llm_prompt},
    )

    reclaimed = schedules.reclaim_orphaned_instance("instance-a", "instance-b")
    assert reclaimed == {"schedules": 1, "events": 0}

    events = queue.Queue()
    SchedulerService(
        events,
        store=schedules,
        run_store=runs,
        instance_id="instance-b",
        poll_interval_s=0.1,
    )._fire_due_items()

    event = events.get_nowait()
    assert event["run_id"] == original_run.run_id
    assert len(runs.list(schedule_id=item.id)) == 1


def test_reclaim_redelivers_event_queued_but_not_dequeued_before_crash(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    _add_due_schedule(schedules, "outbox-before-dequeue", "instance-a")

    abandoned_queue = queue.Queue()
    SchedulerService(
        abandoned_queue,
        store=schedules,
        run_store=runs,
        instance_id="instance-a",
        poll_interval_s=0.1,
    )._fire_due_items()

    assert abandoned_queue.qsize() == 1
    pending = schedules.list_events("pending")
    assert len(pending) == 1
    assert pending[0]["claim_owner"] == "instance-a"

    reclaimed = schedules.reclaim_orphaned_instance("instance-a", "instance-b")
    assert reclaimed == {"schedules": 0, "events": 1}

    recovered_queue = queue.Queue()
    SchedulerService(
        recovered_queue,
        store=schedules,
        run_store=runs,
        instance_id="instance-b",
        poll_interval_s=0.1,
    )._fire_due_items()

    event = recovered_queue.get_nowait()
    assert event["schedule_id"] == "outbox-before-dequeue"
    assert event["owner_instance_id"] == "instance-b"
    assert event["reclaimed_from_instance_id"] == "instance-a"
    assert schedules.list_events("pending") == []


def test_outbox_rows_are_not_written_when_schedule_claim_is_lost(tmp_path):
    schedules = SchedulerStore(tmp_path / "schedules.sqlite3")
    _add_due_schedule(schedules, "outbox-4", "instance-a")

    due = schedules.claim_due_items("instance-a", utc_now())
    assert len(due) == 1
    item, due_at = due[0]
    event = {
        "kind": "user",
        "text": item.effective_prompt,
        "schedule_id": item.id,
        "schedule_type": item.type,
        "schedule_at": due_at,
        "run_id": "run-outbox-4",
        "owner_instance_id": item.owner_instance_id,
        "session_id": item.session_id,
    }

    assert not schedules.finalize_claim_with_events(
        item.id,
        "instance-b",
        None,
        [event],
    )
    assert schedules.list_events() == []
    assert schedules.get_item(item.id) is not None

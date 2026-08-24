from __future__ import annotations

from datetime import timedelta
import queue

from uagent.scheduler import (
    SCHEDULE_TYPE_ONCE,
    ScheduleItem,
    SchedulerRunStore,
    SchedulerService,
    SchedulerStore,
    SchedulerWorker,
    format_iso_datetime,
    utc_now,
)


def test_due_event_can_be_completed_by_worker(tmp_path):
    events = queue.Queue()
    schedules = SchedulerStore(tmp_path / "schedules.json")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    item = ScheduleItem(
        id="integration-1",
        type=SCHEDULE_TYPE_ONCE,
        at=format_iso_datetime(utc_now() - timedelta(seconds=1)),
        llm_prompt="run integration",
        retry_limit=1,
        timeout_sec=2,
    )
    schedules.add_item(item)

    service = SchedulerService(events, store=schedules, run_store=runs)
    service._fire_due_items()
    event = events.get_nowait()
    assert event["run_id"]
    assert event["schedule_at"] == item.at

    run = runs.get(event["run_id"])
    assert run.status == "queued"
    assert run.metadata["llm_prompt"] == "run integration"

    SchedulerWorker(runs).execute(
        run.run_id,
        lambda payload: {"prompt": payload["llm_prompt"]},
        timeout_sec=run.metadata["timeout_sec"],
        retry_limit=run.metadata["retry_limit"],
    )
    completed = runs.get(run.run_id)
    assert completed.status == "success"
    assert completed.attempt == 1

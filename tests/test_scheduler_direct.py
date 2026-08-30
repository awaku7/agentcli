from __future__ import annotations

import json
import queue
from datetime import timedelta

import pytest

from uagent.scheduler import (
    SCHEDULE_TYPE_ONCE,
    ScheduleItem,
    SchedulerRunStore,
    SchedulerService,
    SchedulerStore,
    execute_direct_tool,
    format_iso_datetime,
    utc_now,
)


def test_execute_direct_tool_dispatches_explicit_tool(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_run_tool(name, arguments):
        calls.append((name, arguments))
        return json.dumps({"ok": True, "value": 4})

    monkeypatch.setattr("uagent.tools.run_tool", fake_run_tool)

    assert execute_direct_tool("calculator", {"expression": "2+2"}) == {
        "ok": True,
        "value": 4,
    }
    assert calls == [("calculator", {"expression": "2+2"})]


def test_execute_direct_tool_rejects_arbitrary_execution():
    with pytest.raises(ValueError, match="not allowed"):
        execute_direct_tool("python_exec", {"code": "print(1)"})


def test_service_restores_due_item_when_run_store_fails(tmp_path):
    events = queue.Queue()
    schedules = SchedulerStore(tmp_path / "schedules.json")
    item = ScheduleItem(
        id="restore-1",
        type=SCHEDULE_TYPE_ONCE,
        at=format_iso_datetime(utc_now() - timedelta(seconds=1)),
        execution_mode="direct",
        target_tool="calculator",
    )
    schedules.add_item(item)

    class FailingRunStore:
        def create(self, *_args, **_kwargs):
            raise OSError("temporary run-store failure")

    SchedulerService(
        events, store=schedules, run_store=FailingRunStore()
    )._fire_due_items()
    assert events.empty()
    restored = schedules.get_item("restore-1")
    assert restored is not None
    assert restored.next_fire_at <= utc_now()


def test_direct_schedule_emits_direct_event_and_persists_target(tmp_path):
    events = queue.Queue()
    schedules = SchedulerStore(tmp_path / "schedules.json")
    runs = SchedulerRunStore(tmp_path / "runs.json")
    schedules.add_item(
        ScheduleItem(
            id="direct-1",
            type=SCHEDULE_TYPE_ONCE,
            at=format_iso_datetime(utc_now() - timedelta(seconds=1)),
            execution_mode="direct",
            target_tool="calculator",
            target_args={"expression": "2+2"},
        )
    )

    SchedulerService(events, store=schedules, run_store=runs)._fire_due_items()
    event = events.get_nowait()
    assert event["kind"] == "scheduled_direct"
    run = runs.get(event["run_id"])
    assert run.metadata["execution_mode"] == "direct"
    assert run.metadata["target_tool"] == "calculator"
    assert run.metadata["target_args"] == {"expression": "2+2"}

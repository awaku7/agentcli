from __future__ import annotations

import asyncio

from uagent.a2a.task_store import InMemoryTaskStore, TaskRecord, TaskStatus


def test_task_store_allows_only_documented_transitions() -> None:
    store = InMemoryTaskStore()
    store.create(TaskRecord(id="t1"))

    assert store.transition("t1", "IN_PROGRESS", "CANCEL_REQUESTED") is not None
    assert store.transition("t1", "CANCEL_REQUESTED", "CANCELLED") is not None
    assert store.transition("t1", "CANCELLED", "SUCCEEDED") is None
    assert store.get("t1").status == TaskStatus.CANCELLED.value


def test_late_worker_completion_cannot_overwrite_cancel() -> None:
    store = InMemoryTaskStore()
    store.create(TaskRecord(id="t2"))
    store.transition("t2", "IN_PROGRESS", "CANCEL_REQUESTED")
    store.transition("t2", "CANCEL_REQUESTED", "CANCELLED")

    assert store.transition("t2", "IN_PROGRESS", "FAILED", error={"code": "late"}) is None
    assert store.get("t2").status == "CANCELLED"


def test_runtime_handle_is_stored_without_being_api_data() -> None:
    from uagent.a2a.task_store import TaskRuntime

    store = InMemoryTaskStore()
    store.create(TaskRecord(id="t3"))
    runtime = TaskRuntime(cancel_event=asyncio.Event(), locale="ja")
    assert store.register_runtime("t3", runtime)
    assert store.runtime("t3") is runtime
    assert not hasattr(store.get("t3"), "asyncio_task")

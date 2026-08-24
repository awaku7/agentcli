from __future__ import annotations

import pytest

from uagent.scheduler import SchedulerRunStore


def test_run_store_persists_lifecycle(tmp_path):
    path = tmp_path / "runs.json"
    store = SchedulerRunStore(path)

    run = store.create("schedule-1", idempotency_key="schedule-1:2025-01-01T00:00:00Z")
    assert run.status == "queued"
    assert store.start(run.run_id).status == "running"
    finished = store.finish(run.run_id, result={"ok": True})

    assert finished.status == "success"
    assert finished.attempt == 1
    assert finished.finished_at
    assert SchedulerRunStore(path).get(run.run_id).result == {"ok": True}


def test_idempotency_key_returns_existing_run(tmp_path):
    store = SchedulerRunStore(tmp_path / "runs.json")
    first = store.create("schedule-1", idempotency_key="same")
    second = store.create("schedule-1", idempotency_key="same")

    assert second.run_id == first.run_id
    assert len(store.list()) == 1


def test_run_store_lists_newest_first_and_rejects_invalid_status(tmp_path):
    store = SchedulerRunStore(tmp_path / "runs.json")
    first = store.create("schedule-1")
    second = store.create("schedule-1")
    assert [run.run_id for run in store.list()] == [second.run_id, first.run_id]

    with pytest.raises(ValueError):
        store.finish(first.run_id, status="unknown")


def test_corrupt_store_is_recovered_as_empty(tmp_path):
    path = tmp_path / "runs.json"
    path.write_text("not json", encoding="utf-8")
    assert SchedulerRunStore(path).list() == []

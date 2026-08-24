from __future__ import annotations

import time

import pytest

from uagent.scheduler import SchedulerRunStore, SchedulerWorker


def test_worker_retries_then_succeeds(tmp_path):
    store = SchedulerRunStore(tmp_path / "runs.json")
    run = store.create("s1")
    calls = []

    def execute(payload):
        calls.append(payload["run_id"])
        if len(calls) == 1:
            raise ValueError("temporary")
        return {"ok": True}

    assert SchedulerWorker(store).execute(run.run_id, execute, retry_limit=1) == {
        "ok": True
    }
    saved = store.get(run.run_id)
    assert saved.status == "success"
    assert saved.attempt == 2


def test_worker_records_terminal_failure(tmp_path):
    store = SchedulerRunStore(tmp_path / "runs.json")
    run = store.create("s1")

    with pytest.raises(RuntimeError, match="permanent"):
        SchedulerWorker(store).execute(
            run.run_id, lambda _: (_ for _ in ()).throw(ValueError("permanent"))
        )

    saved = store.get(run.run_id)
    assert saved.status == "failed"
    assert saved.error == "permanent"


def test_worker_records_timeout(tmp_path):
    store = SchedulerRunStore(tmp_path / "runs.json")
    run = store.create("s1")

    def slow(_):
        time.sleep(0.2)

    with pytest.raises(RuntimeError, match="timed out"):
        SchedulerWorker(store).execute(run.run_id, slow, timeout_sec=0.01)

    assert store.get(run.run_id).status == "timeout"

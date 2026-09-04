from __future__ import annotations

from uagent.a2a.task_store import SQLiteTaskStore, TaskRecord, TaskStatus


def test_sqlite_task_store_round_trip_and_list(tmp_path) -> None:
    store = SQLiteTaskStore(tmp_path / "tasks.sqlite3")
    record = TaskRecord(
        id="sqlite-1",
        input_message={"role": "user", "content": "hello"},
    )

    store.create(record)
    loaded = store.get("sqlite-1")

    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.input_message == record.input_message
    assert [item.id for item in store.list()] == ["sqlite-1"]


def test_sqlite_task_store_survives_reopen(tmp_path) -> None:
    path = tmp_path / "tasks.sqlite3"
    SQLiteTaskStore(path).create(TaskRecord(id="persisted"))

    reopened = SQLiteTaskStore(path)

    assert reopened.get("persisted").status == TaskStatus.IN_PROGRESS.value


def test_sqlite_task_store_transition_is_compare_and_set(tmp_path) -> None:
    store = SQLiteTaskStore(tmp_path / "tasks.sqlite3")
    store.create(TaskRecord(id="transition"))

    assert (
        store.transition(
            "transition",
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.SUCCEEDED.value,
            output_message={"role": "assistant", "content": "ok"},
        )
        is not None
    )
    assert (
        store.transition(
            "transition",
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.FAILED.value,
        )
        is None
    )
    assert store.get("transition").status == TaskStatus.SUCCEEDED.value


def test_sqlite_task_store_update_does_not_overwrite_status(tmp_path) -> None:
    store = SQLiteTaskStore(tmp_path / "tasks.sqlite3")
    store.create(TaskRecord(id="update"))

    assert store.update("update", status=TaskStatus.SUCCEEDED.value) is None
    updated = store.update("update", error={"code": "E1"})
    assert updated is not None
    assert updated.error == {"code": "E1"}
    assert store.get("update").status == TaskStatus.IN_PROGRESS.value


def test_sqlite_task_store_uses_wal_and_query_indexes(tmp_path) -> None:
    store = SQLiteTaskStore(tmp_path / "tasks.sqlite3")
    with store._connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert {"idx_tasks_created_id", "idx_tasks_status_updated"} <= indexes


def test_sqlite_task_store_recovers_incomplete_tasks_after_restart(tmp_path) -> None:
    path = tmp_path / "tasks.sqlite3"
    store = SQLiteTaskStore(path)
    store.create(TaskRecord(id="interrupted"))
    reopened = SQLiteTaskStore(path)

    recovered = reopened.recover_incomplete()

    assert [item.id for item in recovered] == ["interrupted"]
    record = reopened.get("interrupted")
    assert record.status == TaskStatus.FAILED.value
    assert record.error == {"code": "TASK_INTERRUPTED_BY_RESTART"}
    assert reopened.recover_incomplete() == []


def test_sqlite_task_store_checkpoint_round_trip(tmp_path) -> None:
    store = SQLiteTaskStore(tmp_path / "tasks.sqlite3")
    store.create(TaskRecord(id="checkpoint"))

    assert (
        store.save_checkpoint("checkpoint", {"step": 2, "messages": ["ok"]}) is not None
    )
    assert store.load_checkpoint("checkpoint") == {"step": 2, "messages": ["ok"]}

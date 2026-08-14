from __future__ import annotations

from uagent.a2a.server import _build_task_store
from uagent.a2a.task_store import InMemoryTaskStore, SQLiteTaskStore


def test_task_store_config_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_TASK_STORE", raising=False)
    assert isinstance(_build_task_store(), InMemoryTaskStore)


def test_task_store_config_supports_sqlite(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UAGENT_TASK_STORE", "sqlite")
    monkeypatch.setenv("UAGENT_TASK_STORE_PATH", str(tmp_path / "tasks.db"))
    store = _build_task_store()
    assert isinstance(store, SQLiteTaskStore)
    assert (tmp_path / "tasks.db").exists()

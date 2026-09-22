from __future__ import annotations

import json
from pathlib import Path


def test_new_personal_records_store_owner_and_project(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools import long_memory
    from uagent.tools.add_long_memory_tool import run_tool as add_long_memory

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp_path / "personal.jsonl"))
    monkeypatch.setenv("UAGENT_MEMORY_OWNER", "alice")
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "app")

    assert "saved" in add_long_memory({"note": "personal rule"}).lower()
    record = long_memory.load_long_memory_records()[0]

    assert record["owner"] == "alice"
    assert record["project"] == "app"
    assert record["memory_id"]


def test_new_personal_records_default_owner_to_os_login(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.runtime import memory_scope
    from uagent.tools import long_memory
    from uagent.tools.add_long_memory_tool import run_tool as add_long_memory

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp_path / "personal.jsonl"))
    monkeypatch.delenv("UAGENT_MEMORY_OWNER", raising=False)
    monkeypatch.delenv("USERDOMAIN", raising=False)
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "app")
    monkeypatch.setattr(memory_scope.getpass, "getuser", lambda: "alice")

    assert "saved" in add_long_memory({"note": "personal rule"}).lower()
    record = long_memory.load_long_memory_records()[0]

    assert record["owner"] == "alice"
    assert record["project"] == "app"


def test_new_shared_records_store_owner_and_project(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.tools.add_shared_memory_tool import run_tool as add_shared_memory

    path = tmp_path / "shared.jsonl"
    monkeypatch.setenv("UAGENT_SHARED_MEMORY_FILE", str(path))
    monkeypatch.setenv("UAGENT_MEMORY_OWNER", "alice")
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "app")

    assert "appended" in add_shared_memory({"note": "shared rule"}).lower()
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["owner"] == "alice"
    assert record["project"] == "app"
    assert record["memory_id"]

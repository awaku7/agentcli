from __future__ import annotations

import json
from pathlib import Path


def test_server_workspace_project_uses_captured_workdir_not_mutable_env(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.runtime import memory_scope, runtime_workdir

    captured = tmp_path / "captured-workspace"
    configured = tmp_path / "configured-workspace"
    monkeypatch.setattr(
        runtime_workdir, "get_captured_startup_workdir", lambda: str(captured)
    )
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "")
    monkeypatch.delenv("UAGENT_WORKDIR", raising=False)
    assert memory_scope.resolve_server_workspace_project() == "captured-workspace"

    monkeypatch.setenv("UAGENT_WORKDIR", str(configured))
    assert memory_scope.resolve_server_workspace_project() == "captured-workspace"

    monkeypatch.setattr(runtime_workdir, "get_captured_startup_workdir", lambda: "")
    assert memory_scope.resolve_server_workspace_project() == ""


def test_apply_workdir_captures_canonical_workspace_for_relative_paths(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.runtime import memory_scope, runtime_workdir

    monkeypatch.chdir(tmp_path)
    (tmp_path / "nested").mkdir()
    for relative in (".", "nested/.."):
        monkeypatch.setattr(runtime_workdir, "_STARTUP_WORKDIR", None)
        runtime_workdir.apply_workdir(
            runtime_workdir.decide_workdir(env_workdir=relative)
        )
        assert runtime_workdir.get_captured_startup_workdir() == str(tmp_path.resolve())
        assert memory_scope.resolve_server_workspace_project() == tmp_path.name

    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    assert memory_scope.resolve_server_workspace_project() == tmp_path.name


def test_memory_tools_use_canonical_startup_project(
    tmp_path: Path, monkeypatch
) -> None:
    from uagent.runtime import memory_scope, runtime_workdir
    from uagent.tools import long_memory, shared_memory

    monkeypatch.chdir(tmp_path)
    (tmp_path / "nested").mkdir()
    monkeypatch.setattr(runtime_workdir, "_STARTUP_WORKDIR", None)
    runtime_workdir.apply_workdir(
        runtime_workdir.decide_workdir(env_workdir="nested/..")
    )
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "")
    monkeypatch.setenv("UAGENT_WORKDIR", "nested/..")
    monkeypatch.setenv("UAGENT_MEMORY_OWNER", "alice")
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    personal = tmp_path / "personal.jsonl"
    shared = tmp_path / "shared.jsonl"
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(personal))
    monkeypatch.setenv("UAGENT_SHARED_MEMORY_FILE", str(shared))

    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    assert memory_scope.resolve_memory_project() == tmp_path.name
    assert long_memory.append_long_memory("personal note")
    shared_memory.append_shared_memory("shared note")
    personal_row = json.loads(personal.read_text(encoding="utf-8"))
    shared_row = json.loads(shared.read_text(encoding="utf-8"))
    assert personal_row["project"] == shared_row["project"] == tmp_path.name

    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "explicit")
    assert memory_scope.resolve_memory_project() == "explicit"


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

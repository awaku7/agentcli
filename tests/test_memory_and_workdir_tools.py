from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def _loads_json(s: str) -> dict:
    obj = json.loads(s)
    assert isinstance(obj, dict)
    return obj


def test_add_get_long_memory_roundtrip(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools.add_long_memory_tool import run_tool as add_long_memory
    from uagent.tools.get_long_memory_tool import run_tool as get_long_memory

    mem = repo_tmp_path / "mem.jsonl"
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(mem))

    out1 = add_long_memory({"note": "note-1"})
    assert "saved" in out1.lower()

    out2 = get_long_memory({})
    assert isinstance(out2, str)
    assert "note-1" in out2


def test_add_long_memory_rejects_empty_note(
    monkeypatch: pytest.MonkeyPatch, repo_tmp_path: Path
) -> None:
    from uagent.tools.add_long_memory_tool import run_tool as add_long_memory

    mem = repo_tmp_path / "mem.jsonl"
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(mem))

    out = add_long_memory({"note": "   "})
    assert "error" in out.lower() or "empty" in out.lower()


def test_add_get_shared_memory_roundtrip(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools.add_shared_memory_tool import run_tool as add_shared_memory
    from uagent.tools.get_shared_memory_tool import run_tool as get_shared_memory

    shared = repo_tmp_path / "shared.jsonl"
    monkeypatch.setenv("UAGENT_SHARED_MEMORY_FILE", str(shared))

    out1 = add_shared_memory({"note": "shared-1"})
    assert "appended" in out1.lower() or "1" in out1

    out2 = get_shared_memory({})
    assert isinstance(out2, str)
    assert "shared-1" in out2


def test_add_shared_memory_empty_note_is_noop(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools.add_shared_memory_tool import run_tool as add_shared_memory

    shared = repo_tmp_path / "shared.jsonl"
    monkeypatch.setenv("UAGENT_SHARED_MEMORY_FILE", str(shared))

    out = add_shared_memory({"note": ""})
    assert "nothing saved" in out.lower()


def test_change_workdir_confirm_false(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools.change_workdir_tool import run_tool as change_workdir

    # ensure we restore cwd after the test
    old = Path.cwd()
    try:
        out = change_workdir({"new_dir": str(repo_tmp_path), "confirm": False})
        assert Path(out).resolve() == repo_tmp_path.resolve()
        assert Path.cwd().resolve() == repo_tmp_path.resolve()
    finally:
        os.chdir(old)


def test_change_workdir_confirm_true_accepts_y(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.tools.change_workdir_tool import run_tool as change_workdir

    def fake_human_ask(_args: dict) -> str:
        return json.dumps(
            {
                "tool": "human_ask",
                "message": "x",
                "user_reply": "y",
                "display_reply": "y",
                "cancelled": False,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr("uagent.tools.human_ask_tool.run_tool", fake_human_ask)

    old = Path.cwd()
    try:
        out = change_workdir({"new_dir": str(repo_tmp_path), "confirm": True})
        payload = _loads_json(out)
        # change_workdir returns json when cancelled, plain path otherwise
        assert payload.get("cancelled") is True  # if this happens, the stub isn't used
        raise AssertionError("unexpected cancellation")
    except json.JSONDecodeError:
        # expected: returns the new cwd as string
        assert Path.cwd().resolve() == repo_tmp_path.resolve()
    finally:
        os.chdir(old)

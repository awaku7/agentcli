from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest


def _use_jsonl(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp / "mem.jsonl"))


def _messages(user_turns: int) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": "sys"}]
    for index in range(user_turns):
        messages.append({"role": "user", "content": f"質問 {index}"})
        messages.append({"role": "assistant", "content": f"回答 {index}"})
    return messages


def _record_worker(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    from uagent.runtime import memory_consolidation

    calls: list[int] = []

    def _fake_worker(messages, core, owner="", project=""):  # noqa: ANN001, ANN202
        calls.append(len(messages))

    monkeypatch.setattr(memory_consolidation, "_consolidation_worker", _fake_worker)
    return calls


def _wait_for(calls: list[int], count: int) -> None:
    for _ in range(60):
        if len(calls) >= count:
            return
        time.sleep(0.05)
    raise AssertionError(f"expected {count} worker calls, got {len(calls)}")


def _settle() -> None:
    # Let the tracked worker wrapper release its in-flight slot.
    time.sleep(0.2)


def test_session_end_gate_requires_two_user_turns(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    calls = _record_worker(monkeypatch)

    memory_consolidation.run_session_end_consolidation(
        _messages(1), core=None, session_id="s-short"
    )
    _settle()
    assert calls == []

    memory_consolidation.run_session_end_consolidation(
        _messages(2), core=None, session_id="s-long"
    )
    _wait_for(calls, 1)


def test_session_end_watermark_blocks_repeat_passes(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    calls = _record_worker(monkeypatch)
    messages = _messages(2)

    memory_consolidation.run_session_end_consolidation(
        messages, core=None, session_id="s1"
    )
    _wait_for(calls, 1)
    _settle()

    # The same session, unchanged: no second provider call.
    memory_consolidation.run_session_end_consolidation(
        messages, core=None, session_id="s1"
    )
    _settle()
    assert len(calls) == 1

    # The session grew (it was resumed and continued): a new pass runs.
    memory_consolidation.run_session_end_consolidation(
        _messages(3), core=None, session_id="s1"
    )
    _wait_for(calls, 2)


class _FakeStore:
    def __init__(self, rows: list[dict[str, Any]], messages: dict[str, list]) -> None:
        self._rows = rows
        self._messages = messages

    def list_sessions(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._messages.get(session_id, []))


def _row(session_id: str, project: str = "proj-a", entry_point: str = "cli") -> dict:
    return {
        "session_id": session_id,
        "project": project,
        "entry_point": entry_point,
    }


def test_startup_catches_up_previous_session(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation, memory_scope

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.setattr(memory_scope, "resolve_memory_project", lambda: "proj-a")
    calls = _record_worker(monkeypatch)

    store = _FakeStore(
        [_row("current"), _row("prev")],
        {"prev": _messages(2)},
    )
    memory_consolidation.run_startup_consolidation(
        None, store, current_session_id="current"
    )
    _wait_for(calls, 1)
    _settle()

    # A second startup with the same stored session does not re-run.
    memory_consolidation.run_startup_consolidation(
        None, store, current_session_id="current"
    )
    _settle()
    assert len(calls) == 1


def test_startup_skips_other_projects_and_sub_agents(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation, memory_scope

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.setattr(memory_scope, "resolve_memory_project", lambda: "proj-a")
    calls = _record_worker(monkeypatch)

    other_project = _FakeStore(
        [_row("current"), _row("prev", project="proj-b")],
        {"prev": _messages(2)},
    )
    memory_consolidation.run_startup_consolidation(
        None, other_project, current_session_id="current"
    )
    _settle()
    assert calls == []

    with_sub_agent = _FakeStore(
        [_row("current"), _row("sub", entry_point="sub-agent"), _row("prev")],
        {"sub": _messages(3), "prev": _messages(2)},
    )
    memory_consolidation.run_startup_consolidation(
        None, with_sub_agent, current_session_id="current"
    )
    _wait_for(calls, 1)


def test_switch_hook_passes_outgoing_messages(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent import util_cmd_session
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    seen: list[tuple[int, str]] = []

    def _fake_run(messages, core, *, session_id=""):  # noqa: ANN001, ANN202
        seen.append((len(messages), session_id))

    monkeypatch.setattr(
        memory_consolidation, "run_session_end_consolidation", _fake_run
    )

    class _Core:
        session_id = "outgoing-1"
        _session_store_active_id = "outgoing-1"

    messages = _messages(2)
    util_cmd_session._consolidate_outgoing_session(messages, core=_Core())
    assert seen == [(len(messages), "outgoing-1")]

    def _boom(messages, core, *, session_id=""):  # noqa: ANN001, ANN202
        raise RuntimeError("nope")

    monkeypatch.setattr(memory_consolidation, "run_session_end_consolidation", _boom)
    # A failing consolidation hook must never break the switch itself.
    util_cmd_session._consolidate_outgoing_session(messages, core=_Core())

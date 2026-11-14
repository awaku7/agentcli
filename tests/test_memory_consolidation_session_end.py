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
        return True

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


def test_failed_pass_leaves_session_eligible_for_retry(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    calls: list[int] = []
    outcome = {"ok": False}

    def _fake_worker(messages, core, owner="", project=""):  # noqa: ANN001, ANN202
        calls.append(len(messages))
        return outcome["ok"]

    monkeypatch.setattr(memory_consolidation, "_consolidation_worker", _fake_worker)
    messages = _messages(2)

    # The pass ran but did not complete: no watermark is recorded, so
    # the next trigger retries instead of skipping the session forever.
    memory_consolidation.run_session_end_consolidation(
        messages, core=None, session_id="s-retry"
    )
    _wait_for(calls, 1)
    _settle()
    memory_consolidation.run_session_end_consolidation(
        messages, core=None, session_id="s-retry"
    )
    _wait_for(calls, 2)
    _settle()

    # Once a pass completes, the watermark takes over and blocks repeats.
    outcome["ok"] = True
    memory_consolidation.run_session_end_consolidation(
        messages, core=None, session_id="s-retry"
    )
    _wait_for(calls, 3)
    _settle()
    memory_consolidation.run_session_end_consolidation(
        messages, core=None, session_id="s-retry"
    )
    _settle()
    assert len(calls) == 3


def test_session_end_coverage_survives_history_compression(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    calls = _record_worker(monkeypatch)

    full = _messages(4)
    memory_consolidation.run_session_end_consolidation(
        full, core=None, session_id="s-comp"
    )
    _wait_for(calls, 1)
    _settle()

    # The session was resumed and its history compressed: the list is
    # now SHORTER than the recorded count, but it ends with new turns.
    # A bare count watermark would suppress this pass forever.
    compressed = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "（これまでの要約）"},
        *full[-2:],
        {"role": "user", "content": "新しい質問"},
        {"role": "assistant", "content": "新しい回答"},
    ]
    assert len(compressed) < len(full)
    memory_consolidation.run_session_end_consolidation(
        compressed, core=None, session_id="s-comp"
    )
    _wait_for(calls, 2)
    _settle()

    # The same compressed state again: covered, no third pass.
    memory_consolidation.run_session_end_consolidation(
        compressed, core=None, session_id="s-comp"
    )
    _settle()
    assert len(calls) == 2


def test_startup_skips_principal_and_room_sessions(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation, memory_scope

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.setattr(memory_scope, "resolve_memory_project", lambda: "proj-a")
    calls = _record_worker(monkeypatch)

    # Web-principal and room sessions in the same project are not the
    # local owner's conversations and must never be caught up into
    # the local memory.
    bound_only = _FakeStore(
        [
            _row("current"),
            _row("web-user", principal_id="user-1"),
            _row("room-chat", room_id="room-1"),
        ],
        {"web-user": _messages(3), "room-chat": _messages(3)},
    )
    memory_consolidation.run_startup_consolidation(
        None, bound_only, current_session_id="current"
    )
    _settle()
    assert calls == []

    # A local session behind the bound ones is still reached.
    mixed = _FakeStore(
        [
            _row("current"),
            _row("web-user", principal_id="user-1"),
            _row("prev"),
        ],
        {"web-user": _messages(3), "prev": _messages(2)},
    )
    memory_consolidation.run_startup_consolidation(
        None, mixed, current_session_id="current"
    )
    _wait_for(calls, 1)
    assert calls == [len(_messages(2))]


class _FakeStore:
    def __init__(self, rows: list[dict[str, Any]], messages: dict[str, list]) -> None:
        self._rows = rows
        self._messages = messages

    def list_sessions(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        for row in self._rows:
            if row.get("session_id") == session_id:
                return dict(row)
        return None

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._messages.get(session_id, []))


def _row(
    session_id: str,
    project: str = "proj-a",
    entry_point: str = "cli",
    principal_id: str = "",
    room_id: str = "",
) -> dict:
    return {
        "session_id": session_id,
        "project": project,
        "entry_point": entry_point,
        "principal_id": principal_id,
        "room_id": room_id,
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


def test_startup_reaches_older_session_behind_other_project(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation, memory_scope

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.setattr(memory_scope, "resolve_memory_project", lambda: "proj-a")
    calls = _record_worker(monkeypatch)

    # The newest other session belongs to another project; the older
    # same-project session behind it must still be caught up.
    store = _FakeStore(
        [_row("current"), _row("newer-other", project="proj-b"), _row("older-same")],
        {"newer-other": _messages(3), "older-same": _messages(2)},
    )
    memory_consolidation.run_startup_consolidation(
        None, store, current_session_id="current"
    )
    _wait_for(calls, 1)
    assert calls == [len(_messages(2))]


def test_startup_filters_by_stored_project_not_memory_override(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation, memory_scope

    _use_jsonl(monkeypatch, repo_tmp_path)
    # UAGENT_MEMORY_PROJECT overrides the *destination* namespace for
    # extracted notes; session rows still carry the path-derived
    # workspace identifier, which must be what filters candidates.
    monkeypatch.setattr(
        memory_scope, "resolve_memory_project", lambda: "memory-override"
    )
    calls = _record_worker(monkeypatch)

    store = _FakeStore(
        [_row("current"), _row("prev")],
        {"prev": _messages(2)},
    )
    memory_consolidation.run_startup_consolidation(
        None, store, current_session_id="current"
    )
    _wait_for(calls, 1)
    assert calls == [len(_messages(2))]


def test_switch_hook_passes_outgoing_messages(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent import util_cmd_session
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    seen: list[tuple[int, str]] = []

    def _fake_run(
        messages, core, *, session_id="", project=None
    ):  # noqa: ANN001, ANN202
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

    def _boom(messages, core, *, session_id="", project=None):  # noqa: ANN001, ANN202
        raise RuntimeError("nope")

    monkeypatch.setattr(memory_consolidation, "run_session_end_consolidation", _boom)
    # A failing consolidation hook must never break the switch itself.
    util_cmd_session._consolidate_outgoing_session(messages, core=_Core())


def test_switch_capture_survives_destination_rebind(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent import util_cmd_session
    from uagent.runtime import memory_consolidation, memory_scope

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.setattr(memory_scope, "resolve_memory_project", lambda: "proj-out")
    seen: list[tuple[int, str, str | None]] = []

    def _fake_run(
        messages, core, *, session_id="", project=None
    ):  # noqa: ANN001, ANN202
        seen.append((len(messages), session_id, project))

    monkeypatch.setattr(
        memory_consolidation, "run_session_end_consolidation", _fake_run
    )

    class _Core:
        session_id = "outgoing-1"
        _session_store_active_id = "outgoing-1"

    core = _Core()
    messages = _messages(2)
    captured = util_cmd_session._capture_outgoing_session(messages, core=core)
    # The load restore now rebinds the core to the destination session.
    core.session_id = "incoming-9"
    core._session_store_active_id = "incoming-9"
    util_cmd_session._consolidate_captured_session(captured, core=core)
    # The pass still belongs to the outgoing session and its project.
    assert seen == [(len(messages), "outgoing-1", "proj-out")]


def test_switch_hook_falls_back_to_log_session_id(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent import util_cmd_session
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    seen: list[tuple[int, str]] = []

    def _fake_run(
        messages, core, *, session_id="", project=None
    ):  # noqa: ANN001, ANN202
        seen.append((len(messages), session_id))

    monkeypatch.setattr(
        memory_consolidation, "run_session_end_consolidation", _fake_run
    )

    class _Core:
        # No SQLite session store (UAGENT_SESSION_STORE=0): only the
        # process log session id identifies the outgoing conversation.
        SESSION_ID = "20261115_001234"

    messages = _messages(2)
    util_cmd_session._consolidate_outgoing_session(messages, core=_Core())
    assert seen == [(len(messages), "20261115_001234")]

from __future__ import annotations

import time
from pathlib import Path

import pytest


def _use_jsonl(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp / "mem.jsonl"))


def test_consolidation_opt_out_switches(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime.memory_consolidation import consolidation_enabled

    _use_jsonl(monkeypatch, repo_tmp_path)
    assert consolidation_enabled() is True
    monkeypatch.setenv("UAGENT_MEMORY_CONSOLIDATION", "0")
    assert consolidation_enabled() is False
    monkeypatch.setenv("UAGENT_MEMORY_CONSOLIDATION", "1")
    monkeypatch.setenv("UAGENT_MEMORY", "0")
    assert consolidation_enabled() is False


def test_parse_notes_variants() -> None:
    from uagent.runtime.memory_consolidation import _parse_notes

    assert _parse_notes('{"notes": ["a", "b"]}') == ["a", "b"]
    assert _parse_notes('```json\n{"notes": ["a"]}\n```') == ["a"]
    assert _parse_notes('["a"]') == ["a"]
    assert _parse_notes("not json") == []
    assert _parse_notes('{"notes": []}') == []
    assert _parse_notes('{"notes": [1, "x", " "]}') == ["x"]


def test_save_consolidation_notes_saves_once_and_reports(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    notes = ["勤務先は大阪の物流会社", "娘の名前は花"]
    assert memory_consolidation.save_consolidation_notes(notes) == 2
    records = long_memory.load_long_memory_records()
    assert {str(r.get("note")) for r in records} == set(notes)
    assert all(r.get("source") == "consolidation" for r in records)

    # The same extraction again saves nothing new.
    assert memory_consolidation.save_consolidation_notes(notes) == 0

    # The pending notice accumulates and drains exactly once.
    assert memory_consolidation.pop_pending_consolidation_count() == 2
    assert memory_consolidation.pop_pending_consolidation_count() == 0


def test_consolidation_cannot_resurrect_forgotten_note(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    assert memory_consolidation.save_consolidation_notes(["住所は京都市"]) == 1
    record = long_memory.load_long_memory_records()[0]
    assert long_memory.delete_long_memory_by_id(str(record["memory_id"])) is True

    assert memory_consolidation.save_consolidation_notes(["住所は京都市"]) == 0
    assert long_memory.load_long_memory_records() == []


def test_consolidation_skips_secrets(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    saved = memory_consolidation.save_consolidation_notes(
        ["api_key = sk-1234567890abcdefghij", "普通のメモ"]
    )
    assert saved == 1
    assert [str(r.get("note")) for r in long_memory.load_long_memory_records()] == [
        "普通のメモ"
    ]


def test_save_consolidation_notes_uses_given_project(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    saved = memory_consolidation.save_consolidation_notes(
        ["プロジェクト固定のメモ"], owner="tester", project="proj-x"
    )
    assert saved == 1
    record = long_memory.load_long_memory_records()[0]
    assert record.get("project") == "proj-x"
    assert record.get("owner") == "tester"


def test_marker_replay_cannot_resurrect_consolidation_note(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Consolidation saves the fact first; the user's identical marker
    # is then just a duplicate and leaves no provenance of its own on
    # the record (its source_id stays the consolidation one). After
    # the user forgets the note, a history rewrite replays the marker:
    # the replay is not fresh intent, so the forget boundary must stop
    # it even though the marker's source_id matches nothing.
    from uagent.runtime import memory_consolidation, memory_marker
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    note = "再演で戻らないメモ"
    assert memory_consolidation.save_consolidation_notes([note]) == 1
    live = memory_marker.save_memory_marker(f"remember: {note}")
    assert live is not None and live.get("reason") == "duplicate"
    record = long_memory.load_long_memory_records()[0]
    assert long_memory.delete_long_memory_by_id(str(record["memory_id"]))
    assert long_memory.load_long_memory_records() == []
    replayed = memory_marker.save_memory_marker(
        f"remember: {note}", allow_scoped=False, replay=True
    )
    assert replayed is not None and not replayed.get("saved")
    assert long_memory.load_long_memory_records() == []
    # The same marker written as a new message is fresh intent.
    fresh = memory_marker.save_memory_marker(f"remember: {note}")
    assert fresh is not None and fresh.get("saved")


def test_run_async_captures_scope_at_launch(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The scope must be resolved on the calling thread, before the
    # worker starts: resolving it at save time would use whatever
    # project is current when the background extraction finishes.
    from uagent.runtime import memory_consolidation

    _use_jsonl(monkeypatch, repo_tmp_path)
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "proj-launch")
    seen: list[tuple[str, str]] = []

    def _fake_worker(messages, core, owner="", project=""):  # noqa: ANN001, ANN202
        seen.append((owner, project))

    monkeypatch.setattr(memory_consolidation, "_consolidation_worker", _fake_worker)
    memory_consolidation.run_memory_consolidation_async(
        [{"role": "user", "content": "hi"}], core=None
    )
    for _ in range(50):
        if seen:
            break
        time.sleep(0.05)
    assert seen and seen[0][1] == "proj-launch"
    assert seen[0][0] != ""


def test_consolidation_worker_uses_core_module_contract(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # make_client() reads helpers such as get_env_url from the core
    # argument; the worker must receive (and pass through) an object
    # that provides them — the assembled uagent.core module does.
    import uagent.core as core_module
    from uagent import profile_manager
    from uagent.providers import util_providers
    from uagent.runtime import memory_consolidation
    from uagent.tools import long_memory

    _use_jsonl(monkeypatch, repo_tmp_path)
    seen: dict[str, bool] = {}

    def _fake_make_client(core):  # noqa: ANN001, ANN202
        seen["has_get_env_url"] = hasattr(core, "get_env_url")
        return ("fake", object(), "fake-model")

    monkeypatch.setattr(util_providers, "make_client", _fake_make_client)
    monkeypatch.setattr(
        profile_manager,
        "_llm_simple_text",
        lambda **kwargs: '{"notes": ["勤務先は大阪の物流会社"]}',
    )
    memory_consolidation._consolidation_worker(
        [{"role": "user", "content": "私は大阪の物流会社で働いています"}],
        core_module,
    )
    assert seen["has_get_env_url"] is True
    assert [str(r.get("note")) for r in long_memory.load_long_memory_records()] == [
        "勤務先は大阪の物流会社"
    ]


def test_run_async_respects_local_boundary(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uagent.runtime import memory_consolidation
    from uagent.runtime.identity_context import TurnContext, bind_turn_context

    _use_jsonl(monkeypatch, repo_tmp_path)
    calls: list[int] = []

    def _fake_worker(messages, core, owner="", project=""):  # noqa: ANN001, ANN202
        calls.append(len(messages))

    monkeypatch.setattr(memory_consolidation, "_consolidation_worker", _fake_worker)

    web_turn = TurnContext(
        principal_id="alice",
        room_id="room-1",
        project_id="demo",
        session_id="s1",
        entry_point="web",
        authenticated=True,
        authn_kind="oidc",
        server_bound_project=True,
    )
    messages = [{"role": "user", "content": "hi"}]
    with bind_turn_context(web_turn):
        memory_consolidation.run_memory_consolidation_async(messages, core=None)
    time.sleep(0.2)
    assert calls == []

    memory_consolidation.run_memory_consolidation_async(messages, core=None)
    for _ in range(50):
        if calls:
            break
        time.sleep(0.05)
    assert calls == [1]

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_invalidate_memory_runtime_clears_memory_and_provider_state() -> None:
    from uagent.runtime.memory_forget import invalidate_memory_runtime

    class Runtime:
        def __init__(self) -> None:
            self.reason = ""

        def clear_continuation(self, reason: str = "clear") -> None:
            self.reason = reason

    runtime = Runtime()
    core = SimpleNamespace(
        memory_generation=4,
        memory_projection_snapshot=object(),
        context_plan=object(),
        context_projection_id="projection-1",
        memory_shadow_last_observation={"candidate": "old"},
        memory_shadow_observations=[{"candidate": "old"}],
        _gemini_cache_needs_refresh=False,
        responses_runtime=runtime,
        responses_state={
            "previous_response_id": "resp_old",
            "active_response_id": "resp_active",
            "_stale_rid_occurred": True,
        },
    )

    generation = invalidate_memory_runtime(core)

    assert generation == 5
    assert core.memory_generation == 5
    assert core.memory_forget_pending is True
    assert core.memory_projection_snapshot is None
    assert core.context_plan is None
    assert core.context_projection_id is None
    assert core.memory_shadow_last_observation is None
    assert core.memory_shadow_observations == []
    assert core._gemini_cache_needs_refresh is True
    assert runtime.reason == "memory_forget"
    assert "previous_response_id" not in core.responses_state
    assert "active_response_id" not in core.responses_state
    assert "_stale_rid_occurred" not in core.responses_state


def test_stale_projection_is_stripped_after_generation_change() -> None:
    from uagent.runtime.memory_projection import (
        MemoryProjectionItem,
        MemoryProjectionSnapshot,
        apply_memory_projection,
    )

    snapshot = MemoryProjectionSnapshot(
        profile_content="[USER PROFILE]\nold profile",
        evidence_items=(
            MemoryProjectionItem(
                scope="personal",
                note="forgotten rule",
                reference="memory:old",
            ),
        ),
        diagnostics={"enabled": True},
        generation=1,
    )
    core = SimpleNamespace(memory_generation=2, _uagent_memory_system_contents={})
    messages = [
        {"role": "system", "content": "[MEMORY EVIDENCE]\nforgotten rule"},
        {"role": "user", "content": "continue"},
    ]

    projected = apply_memory_projection(messages, snapshot, core)

    assert projected == [{"role": "user", "content": "continue"}]


def test_forget_pending_strips_only_personal_startup_memory() -> None:
    from uagent.runtime.memory_projection import apply_memory_projection

    personal = "[LONG MEMORY]\npersonal old rule"
    shared = "[LONG MEMORY]\nshared rule"
    profile = "[USER PROFILE]\nPreferences:\n  - keep profile"
    core = SimpleNamespace(
        memory_forget_pending=True,
        _uagent_memory_system_contents={
            "personal": {personal},
            "shared": {shared},
        },
    )
    messages = [
        {"role": "system", "content": profile},
        {"role": "system", "content": personal},
        {"role": "system", "content": shared},
        {"role": "user", "content": "continue"},
    ]

    projected = apply_memory_projection(messages, None, core)

    assert {str(message.get("content")) for message in projected} == {
        profile,
        shared,
        "continue",
    }


@pytest.mark.parametrize("backend", ["jsonl", "sqlite"])
def test_delete_propagates_and_forgotten_note_does_not_reappear(
    tmp_path, monkeypatch, backend: str
) -> None:
    from uagent.runtime.memory_projection import (
        apply_memory_projection,
        prepare_memory_projection,
    )
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", backend)
    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")
    monkeypatch.setenv("UAGENT_MEMORY_STRICT_SCOPE", "1")
    monkeypatch.setenv("UAGENT_MEMORY_OWNER", "alice")
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "app")
    if backend == "jsonl":
        monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp_path / "memory.jsonl"))
    else:
        monkeypatch.setenv("UAGENT_MEMORY_DB", str(tmp_path / "memory.sqlite3"))

    assert long_memory.append_long_memory("forgotten rule") is True

    core = SimpleNamespace(
        memory_generation=0,
        memory_owner="alice",
        _uagent_memory_system_contents={},
        responses_state={"previous_response_id": "resp_old"},
    )
    messages = [{"role": "user", "content": "forgotten rule"}]
    snapshot = prepare_memory_projection(messages, core)
    assert snapshot is not None
    assert any(item.note == "forgotten rule" for item in snapshot.evidence_items)
    core.memory_projection_snapshot = snapshot

    assert long_memory.delete_long_memory_entry(0, core=core) is True
    assert core.memory_generation == 1
    assert core.memory_forget_pending is True
    assert core.memory_projection_snapshot is None
    assert "previous_response_id" not in core.responses_state

    stale_projection = apply_memory_projection(messages, snapshot, core)
    assert all(
        "forgotten rule" not in str(message.get("content", ""))
        for message in stale_projection
        if message.get("role") == "system"
    )

    fresh_snapshot = prepare_memory_projection(messages, core)
    assert fresh_snapshot is not None
    assert fresh_snapshot.generation == 1
    assert fresh_snapshot.evidence_items == ()

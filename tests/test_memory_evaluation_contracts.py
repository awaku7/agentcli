from __future__ import annotations

import copy
from types import SimpleNamespace


def test_evaluation_covers_frozen_snapshot_reuse(monkeypatch) -> None:
    from uagent.runtime import memory_projection
    from uagent.runtime.memory_projection import (
        apply_memory_projection,
        prepare_memory_projection,
    )
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")
    monkeypatch.setenv("UAGENT_MEMORY_STRICT_SCOPE", "1")
    monkeypatch.setenv("UAGENT_MEMORY_OWNER", "alice")
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "app")
    records = [{"note": "original rule", "owner": "alice", "project": "app"}]
    monkeypatch.setattr(
        long_memory,
        "load_long_memory_records",
        lambda: list(records),
    )
    monkeypatch.setattr(memory_projection, "is_profiling_enabled", lambda: False)
    core = SimpleNamespace(workdir="different", memory_owner="alice")
    messages = [{"role": "user", "content": "rule"}]
    before = copy.deepcopy(messages)

    snapshot = prepare_memory_projection(messages, core)
    records[:] = [{"note": "new rule", "owner": "alice", "project": "app"}]
    projected = apply_memory_projection(messages, snapshot, core)

    assert messages == before
    text = "\n".join(str(message.get("content", "")) for message in projected)
    assert "original rule" in text
    assert "new rule" not in text


def test_evaluation_covers_projection_budget_and_scope_boundary(monkeypatch) -> None:
    from uagent.runtime import memory_projection
    from uagent.runtime.memory_projection import (
        apply_memory_projection,
        prepare_memory_projection,
    )
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")
    monkeypatch.setenv("UAGENT_MEMORY_STRICT_SCOPE", "1")
    monkeypatch.setenv("UAGENT_MEMORY_OWNER", "alice")
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", "app")
    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION_CHARS", "300")
    monkeypatch.setattr(
        long_memory,
        "load_long_memory_records",
        lambda: [
            {
                "note": "database rule " + "x" * 20,
                "owner": "alice",
                "project": "app",
            },
            {
                "note": "wrong project rule",
                "owner": "alice",
                "project": "web",
            },
        ],
    )
    monkeypatch.setattr(memory_projection, "is_profiling_enabled", lambda: False)
    core = SimpleNamespace(workdir="different", memory_owner="alice")
    messages = [{"role": "user", "content": "database rule"}]

    snapshot = prepare_memory_projection(messages, core)
    projected = apply_memory_projection(messages, snapshot, core)

    assert snapshot is not None
    evidence = [
        str(message["content"])
        for message in projected
        if str(message.get("content", "")).startswith("[MEMORY EVIDENCE]")
    ]
    assert len(evidence) == 1
    assert len(evidence[0]) <= 300
    assert "wrong project rule" not in evidence[0]


def test_evaluation_covers_history_boundary_for_derived_context() -> None:
    from uagent.runtime.memory_history_boundary import strip_derived_memory_context

    messages = [
        {"role": "system", "content": "[startup cwd]\nC:\\app"},
        {"role": "system", "content": "[MEMORY EVIDENCE]\n- old rule"},
        {"role": "user", "content": "continue"},
    ]

    filtered = strip_derived_memory_context(messages)

    assert filtered == [messages[0], messages[2]]

from __future__ import annotations

import copy


def test_opt_in_projection_replaces_broad_memory_and_adds_current_profile(
    tmp_path, monkeypatch
) -> None:
    from uagent.runtime import memory_projection
    from uagent.runtime.memory_projection import (
        apply_memory_projection,
        prepare_memory_projection,
    )
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")
    monkeypatch.setenv("UAGENT_MEMORY_BACKEND", "jsonl")
    monkeypatch.setenv("UAGENT_MEMORY_FILE", str(tmp_path / "memory.jsonl"))
    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION_CHARS", "500")
    monkeypatch.setattr(
        long_memory,
        "load_long_memory_records",
        lambda: [
            {
                "note": "database rule",
                "owner": "alice",
                "project": tmp_path.name,
            }
        ],
    )
    monkeypatch.setattr(memory_projection, "is_profiling_enabled", lambda: True)
    monkeypatch.setattr(
        memory_projection,
        "load_profile",
        lambda: {"constraints": ["never expose secrets"], "preferences": ["be concise"]},
    )

    baseline = "[legacy broad memory]\n- database rule"
    core = type("Core", (), {})()
    core.workdir = str(tmp_path)
    core.memory_owner = "alice"
    core._uagent_memory_system_contents = {"personal": {baseline}}
    messages = [
        {"role": "system", "content": "system instruction"},
        {"role": "system", "content": baseline},
        {"role": "user", "content": "help with the database"},
    ]
    before = copy.deepcopy(messages)

    snapshot = prepare_memory_projection(messages, core)
    projected = apply_memory_projection(messages, snapshot, core)

    assert snapshot is not None
    assert messages == before
    contents = [str(message.get("content")) for message in projected]
    assert baseline not in contents
    assert any("[USER PROFILE]" in content for content in contents)
    evidence = [content for content in contents if content.startswith("[MEMORY EVIDENCE]")]
    assert len(evidence) == 1
    assert evidence[0].count("database rule") == 1
    assert len(evidence[0]) <= 500
    diagnostics = snapshot.to_diagnostics()
    assert diagnostics["profile_present"] is True
    assert diagnostics["owner"] == "alice"
    assert diagnostics["project"] == tmp_path.name
    assert diagnostics["session_id"] == "unknown"
    assert diagnostics["source_revision"] == "unknown"
    assert diagnostics["memory_budget_chars"] == 500
    assert diagnostics["memory_budget_used_chars"] <= 500
    assert diagnostics["selection_reasons"]["personal"] == "query_match"

    retried = apply_memory_projection(projected, snapshot, core)
    retried_contents = [str(message.get("content")) for message in retried]
    assert sum(content.startswith("[MEMORY EVIDENCE]") for content in retried_contents) == 1
    assert sum(content.startswith("[USER PROFILE]") for content in retried_contents) == 1


def test_projection_is_disabled_without_explicit_opt_in(monkeypatch) -> None:
    from uagent.runtime.memory_projection import (
        apply_memory_projection,
        prepare_memory_projection,
    )

    monkeypatch.delenv("UAGENT_MEMORY_PROJECTION", raising=False)
    messages = [{"role": "user", "content": "database"}]
    core = type("Core", (), {})()

    assert prepare_memory_projection(messages, core) is None
    projected = apply_memory_projection(messages, None, core)
    assert projected == messages
    assert projected is not messages


def test_projection_diagnostics_are_added_to_context_plan_telemetry() -> None:
    from uagent.runtime.memory_projection import MemoryProjectionSnapshot
    from uagent.uagent_llm import _build_round_context_plan

    class Manager:
        def build_context_plan(self, **kwargs):
            return kwargs

    core = type("Core", (), {})()
    core.context_manager = Manager()
    core.memory_projection_snapshot = MemoryProjectionSnapshot(
        profile_content="[USER PROFILE]\nConstraints: ...",
        evidence_items=(),
        diagnostics={"enabled": True, "evidence_count": 0, "memory_budget_chars": 4000},
    )

    plan = _build_round_context_plan(
        provider="test",
        depname="model",
        call_messages=[{"role": "user", "content": "hello"}],
        core=core,
        workspace_id="workspace",
    )

    assert plan["telemetry"]["memory_projection"]["enabled"] is True
    assert plan["telemetry"]["memory_projection"]["memory_budget_chars"] == 4000


def test_projection_excludes_owner_mismatch_and_unscoped_legacy_records(
    tmp_path, monkeypatch
) -> None:
    from uagent.runtime.memory_projection import (
        apply_memory_projection,
        prepare_memory_projection,
    )
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")
    monkeypatch.setattr(
        long_memory,
        "load_long_memory_records",
        lambda: [
            {
                "note": "allowed database rule",
                "owner": "alice",
                "project": tmp_path.name,
            },
            {
                "note": "other owner database rule",
                "owner": "bob",
                "project": tmp_path.name,
            },
            {"note": "legacy database rule"},
        ],
    )
    core = type("Core", (), {})()
    core.workdir = str(tmp_path)
    core.memory_owner = "alice"
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
    assert "allowed database rule" in evidence[0]
    assert "other owner database rule" not in evidence[0]
    assert "legacy database rule" not in evidence[0]
    reasons = {
        item["reason"] for item in snapshot.diagnostics["personal"]["diagnostics"]
    }
    assert "owner_mismatch" in reasons
    assert "scope_unknown" in reasons

from __future__ import annotations

import json
from pathlib import Path


def _fixture_cases() -> list[dict]:
    fixture = Path(__file__).parent / "fixtures" / "memory_evaluation_cases.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["retrieval_cases"]


def test_v2_evaluation_runner_compares_all_rollout_modes() -> None:
    from uagent.runtime.memory_evaluation_runner import run_evaluation

    report = run_evaluation(
        _fixture_cases(),
        iterations=1,
        projection_chars=4_000,
        gate_mode="strict_scope",
    )

    assert tuple(report["modes"]) == (
        "baseline",
        "shadow",
        "projection",
        "strict_scope",
    )
    assert report["overall_gate_passed"] is True

    baseline = report["modes"]["baseline"]
    projection = report["modes"]["projection"]
    strict_scope = report["modes"]["strict_scope"]

    assert baseline["informational"] is True
    assert baseline["gate_passed"] is None
    assert baseline["irrelevant_injection_rate"] > 0.0
    assert baseline["scope_violation_count"] > 0
    assert baseline["avg_context_chars"] > 0

    assert projection["avg_context_chars"] > 0
    assert (
        projection["irrelevant_injection_rate"] < baseline["irrelevant_injection_rate"]
    )

    assert strict_scope["gate_passed"] is True
    assert strict_scope["recall"] == 1.0
    assert strict_scope["irrelevant_injection_rate"] == 0.0
    assert strict_scope["scope_violation_count"] == 0
    assert strict_scope["legacy_unknown_selected_count"] == 0
    assert strict_scope["forget_reappearance_count"] == 0
    assert strict_scope["provider_continuation_cleared"] is True


def test_runner_report_omits_note_bodies_by_default_and_can_include_them() -> None:
    from uagent.runtime.memory_evaluation_runner import run_evaluation

    cases = _fixture_cases()[:1]
    safe_report = run_evaluation(cases, iterations=1)
    safe_result = safe_report["modes"]["strict_scope"]["results"][0]
    assert "returned_notes" not in safe_result
    assert safe_result["returned_note_hashes"]

    verbose_report = run_evaluation(cases, iterations=1, include_notes=True)
    verbose_result = verbose_report["modes"]["strict_scope"]["results"][0]
    assert verbose_result["returned_notes"] == ["database migration rule"]


def test_runner_markdown_contains_summary_without_memory_note_text() -> None:
    from uagent.runtime.memory_evaluation_runner import render_markdown, run_evaluation

    report = run_evaluation(_fixture_cases(), iterations=1)
    markdown = render_markdown(report)

    assert "# Memory V2 Evaluation Report" in markdown
    assert "| strict_scope |" in markdown
    assert "Overall gate: **PASS**" in markdown
    assert "database migration rule" not in markdown


def test_runner_cli_writes_json_and_markdown(tmp_path) -> None:
    from uagent.runtime.memory_evaluation_runner import main

    fixture = Path(__file__).parent / "fixtures" / "memory_evaluation_cases.json"
    json_out = tmp_path / "report.json"
    markdown_out = tmp_path / "report.md"

    rc = main(
        [
            "--fixture",
            str(fixture),
            "--iterations",
            "1",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--enforce",
        ]
    )

    assert rc == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["overall_gate_passed"] is True
    assert payload["gate_mode"] == "strict_scope"
    assert markdown_out.read_text(encoding="utf-8").startswith(
        "# Memory V2 Evaluation Report"
    )


def test_strict_scope_adjusts_legacy_expectation_instead_of_counting_it_as_loss() -> (
    None
):
    from uagent.runtime.memory_evaluation_runner import evaluate_mode_case

    case = next(
        case for case in _fixture_cases() if case["id"] == "legacy_compatibility"
    )
    result = evaluate_mode_case(case, "strict_scope", iterations=1)

    assert result.expected_count == 0
    assert result.returned_count == 0
    assert result.recall == 1.0
    assert result.passed is True


def test_scope_evaluation_oracle_detects_injected_cross_owner_candidate(
    monkeypatch,
) -> None:
    from uagent.runtime import memory_evaluation
    from uagent.runtime.active_context import ContextCandidate
    from uagent.runtime.memory_retrieval import (
        MemoryShadowDiagnostic,
        MemoryShadowResult,
    )

    item_id = "memory-shadow:unknown:personal:0"
    injected = MemoryShadowResult(
        candidates=[
            ContextCandidate(
                item_id=item_id,
                source="memory",
                section="memory",
                content="private note",
            )
        ],
        diagnostics=[
            MemoryShadowDiagnostic(
                index=0,
                action="candidate",
                reason="query_match",
                item_id=item_id,
                scope_status="scoped",
            )
        ],
        total_records=1,
        eligible_records=1,
        excluded_records=0,
    )
    monkeypatch.setattr(
        memory_evaluation,
        "shadow_retrieve_memories",
        lambda *_args, **_kwargs: injected,
    )

    result = memory_evaluation.evaluate_retrieval_case(
        {
            "id": "cross-owner",
            "query": "private",
            "scope": "personal",
            "owner": "alice",
            "project": "app",
            "records": [
                {
                    "note": "private note",
                    "owner": "bob",
                    "project": "app",
                }
            ],
            "expected_notes": ["private note"],
        }
    )

    assert result.scope_violation_count == 1
    assert result.passed is False
    assert "scope_violation" in result.failure_reasons


def test_scope_evaluation_oracle_rejects_unapproved_grant_revision(monkeypatch) -> None:
    from uagent.runtime import memory_evaluation
    from uagent.runtime.active_context import ContextCandidate
    from uagent.runtime.memory_retrieval import (
        MemoryShadowDiagnostic,
        MemoryShadowResult,
    )

    item_id = "memory-shadow:unknown:personal:0"
    injected = MemoryShadowResult(
        candidates=[
            ContextCandidate(
                item_id=item_id,
                source="memory",
                section="memory",
                content="shared rule",
            )
        ],
        diagnostics=[
            MemoryShadowDiagnostic(
                index=0,
                action="candidate",
                reason="query_match",
                item_id=item_id,
                scope_status="scoped",
            )
        ],
        total_records=1,
        eligible_records=1,
        excluded_records=0,
    )
    monkeypatch.setattr(
        memory_evaluation,
        "shadow_retrieve_memories",
        lambda *_args, **_kwargs: injected,
    )

    result = memory_evaluation.evaluate_retrieval_case(
        {
            "id": "stale-grant-revision",
            "query": "shared rule",
            "scope": "personal",
            "owner": "alice",
            "project": "app",
            "records": [
                {
                    "note": "shared rule",
                    "memory_id": "shared-memory",
                    "revision": 3,
                    "owner": "alice",
                    "project": "app",
                    "audience_type": "personal",
                    "audience_id": "alice",
                }
            ],
            "authorized_memory_revisions": {"shared-memory": 4},
            "expected_notes": ["shared rule"],
        }
    )

    assert result.scope_violation_count == 1
    assert result.passed is False


def test_v3_authorized_outputs_are_checked_against_private_room_and_grant_scope(
    tmp_path,
) -> None:
    from uagent.runtime.memory_access import MemoryAccessContext, ScopedMemoryStore
    from uagent.runtime.memory_evaluation import evaluate_retrieval_case
    from uagent.runtime.memory_store import MemoryStore

    store = MemoryStore(tmp_path / "memory.sqlite3")
    owner = ScopedMemoryStore(
        store,
        MemoryAccessContext(
            principal_id="owner",
            project_id="app",
            authenticated=True,
            private_session=True,
        ),
    )
    recipient = ScopedMemoryStore(
        store,
        MemoryAccessContext(
            principal_id="recipient",
            project_id="app",
            authenticated=True,
            private_session=True,
        ),
    )
    outsider = ScopedMemoryStore(
        store,
        MemoryAccessContext(
            principal_id="outsider",
            project_id="app",
            authenticated=True,
            private_session=True,
        ),
    )
    direct = owner.append("alpha direct grant")
    owner.share(direct["memory_id"], "recipient", expected_revision=1)
    recipient.append("alpha recipient private")
    outsider.append("alpha outsider private")

    room_record = store.append("alpha room audience", owner="owner", project="app")
    store.db.execute(
        "UPDATE memories SET owner_id='owner', audience_type='room', "
        "audience_id='room-X' WHERE memory_id=?",
        (room_record["memory_id"],),
    )
    store.db.commit()
    room_reader = ScopedMemoryStore(
        store,
        MemoryAccessContext(
            principal_id="recipient",
            project_id="app",
            authenticated=True,
            room_id="room-X",
            private_session=False,
            readable_audiences=(("room", "room-X"),),
        ),
    )

    assert direct["memory_id"] in {
        record["memory_id"] for record in recipient.records()
    }
    owner.update(direct["memory_id"], "alpha direct grant revised", expected_revision=1)

    authorized_records = recipient.records() + room_reader.records()
    authorized_revisions = {
        str(record["memory_id"]): record["revision"] for record in authorized_records
    }
    accepted = evaluate_retrieval_case(
        {
            "id": "v3-authorized-output",
            "query": "alpha",
            "scope": "personal",
            "project": "app",
            "records": authorized_records,
            "authorized_memory_revisions": authorized_revisions,
            "expected_notes": [record["note"] for record in authorized_records],
        }
    )
    assert accepted.passed is True
    assert accepted.scope_violation_count == 0

    # The raw repository contains a stale direct grant and another principal's
    # private record. Neither is in the authoritative scoped output/revision map.
    rejected = evaluate_retrieval_case(
        {
            "id": "v3-overbroad-output",
            "query": "alpha",
            "scope": "personal",
            "project": "app",
            "records": store.records(),
            "authorized_memory_revisions": authorized_revisions,
            "expected_notes": [record["note"] for record in authorized_records],
        }
    )
    assert rejected.passed is False
    assert rejected.scope_violation_count >= 2
    store.close()

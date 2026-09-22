from __future__ import annotations

from uagent.runtime.memory_retrieval import shadow_retrieve_memories


def test_shadow_retrieval_adapts_note_without_metadata_leakage() -> None:
    result = shadow_retrieve_memories(
        [
            {
                "note": "コードは必ず全体を表示する",
                "ts": 10,
                "id": "legacy-id",
                "owner": "alice",
            }
        ],
        query="全体を表示",
        scope="personal",
        owner="alice",
        backend_revision="r1",
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.content == "コードは必ず全体を表示する"
    assert candidate.source == "memory"
    assert candidate.section == "memory"
    assert candidate.relevance and candidate.relevance > 0
    assert candidate.reference == "memory-shadow://personal/0?revision=r1"
    assert "legacy-id" not in result.to_dict().__repr__()


def test_shadow_retrieval_excludes_unrelated_records_before_ranking() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "天気のメモ", "ts": 100},
            {"note": "database migration completed", "ts": 1},
        ],
        query="database migration",
        scope="personal",
    )

    assert [candidate.content for candidate in result.candidates] == [
        "database migration completed"
    ]
    assert result.excluded_records == 1
    assert any(
        item.reason == "no_query_match" and item.action == "exclude"
        for item in result.diagnostics
    )


def test_shadow_retrieval_drops_weak_matches_relative_to_best_candidate() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "V2デモのPython合言葉は COBALT-731"},
            {"note": "V2デモの料理の合言葉は MISO-204。"},
            {"note": "V2デモの旅行の合言葉は RAIL-918。"},
        ],
        query="V2デモのPython合言葉は？",
        scope="personal",
    )

    assert [candidate.content for candidate in result.candidates] == [
        "V2デモのPython合言葉は COBALT-731"
    ]
    assert result.eligible_records == 1
    assert result.excluded_records == 2
    assert (
        sum(
            item.reason == "weak_query_match" and item.action == "exclude"
            for item in result.diagnostics
        )
        == 2
    )


def test_shadow_retrieval_supports_paths_and_short_japanese_queries() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "編集対象は src/uagent/runtime/memory_store.py"},
            {"note": "関係ない記録"},
        ],
        query="memory_store.py",
        scope="personal",
    )

    assert len(result.candidates) == 1
    assert "memory_store.py" in result.candidates[0].content


def test_shadow_retrieval_applies_owner_and_project_boundaries() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "project rule", "owner": "alice", "project": "app"},
            {"note": "other owner", "owner": "bob", "project": "app"},
            {"note": "other project", "owner": "alice", "project": "web"},
            {"note": "legacy project note"},
        ],
        query="project",
        scope="personal",
        owner="alice",
        project="app",
    )

    assert {candidate.content for candidate in result.candidates} == {
        "project rule",
        "legacy project note",
    }
    reasons = {item.reason for item in result.diagnostics if item.action == "exclude"}
    assert {"owner_mismatch", "project_mismatch"} <= reasons
    assert any(item.scope_status == "legacy_unknown" for item in result.diagnostics)


def test_shadow_retrieval_does_not_promote_shared_records() -> None:
    result = shadow_retrieve_memories(
        [{"scope": "shared", "note": "team database rule"}],
        query="database",
        scope="personal",
    )

    assert result.candidates == []
    assert result.diagnostics[0].reason == "scope_mismatch"


def test_shadow_retrieval_deduplicates_notes_and_caps_candidates() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "same decision", "ts": 1},
            {"note": "same decision", "ts": 2},
            {"note": "another decision", "ts": 3},
        ],
        query="decision",
        scope="personal",
        max_candidates=1,
    )

    assert len(result.candidates) == 1
    assert sum(item.reason == "duplicate_note" for item in result.diagnostics) == 1


def test_shadow_retrieval_normalizes_punctuation_before_phrase_ranking() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "V2デモのPython合言葉は COBALT-731"},
            {"note": "V2デモの料理の合言葉は MISO-204。"},
            {"note": "V2デモの旅行の合言葉は RAIL-918。"},
        ],
        query="V2デモの料理の合言葉は？",
        scope="personal",
    )

    assert [candidate.content for candidate in result.candidates] == [
        "V2デモの料理の合言葉は MISO-204。"
    ]
    assert sum(item.reason == "weaker_match_tier" for item in result.diagnostics) == 2


def test_shadow_retrieval_uses_discriminative_fallback_for_japanese() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "V2デモのPython合言葉は COBALT-731"},
            {"note": "V2デモの料理の合言葉は MISO-204。"},
            {"note": "V2デモの旅行の合言葉は RAIL-918。"},
        ],
        query="V2デモの料理合言葉は？",
        scope="personal",
    )

    assert [candidate.content for candidate in result.candidates] == [
        "V2デモの料理の合言葉は MISO-204。"
    ]


def test_shadow_retrieval_uses_discriminative_fallback_for_chinese() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "V2演示的Python口令是 COBALT-731。"},
            {"note": "V2演示的料理口令是 MISO-204。"},
            {"note": "V2演示的旅行口令是 RAIL-918。"},
        ],
        query="V2演示料理口令是什么？",
        scope="personal",
    )

    assert [candidate.content for candidate in result.candidates] == [
        "V2演示的料理口令是 MISO-204。"
    ]


def test_shadow_retrieval_uses_discriminative_fallback_for_thai() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "V2เดโมรหัสPythonคือ COBALT-731"},
            {"note": "V2เดโมรหัสอาหารคือ MISO-204"},
            {"note": "V2เดโมรหัสท่องเที่ยวคือ RAIL-918"},
        ],
        query="V2เดโมรหัสอาหารคืออะไร?",
        scope="personal",
    )

    assert [candidate.content for candidate in result.candidates] == [
        "V2เดโมรหัสอาหารคือ MISO-204"
    ]


def test_shadow_retrieval_keeps_word_based_english_ranking() -> None:
    result = shadow_retrieve_memories(
        [
            {"note": "V2 demo Python passphrase is COBALT-731"},
            {"note": "V2 demo cooking passphrase is MISO-204"},
            {"note": "V2 demo travel passphrase is RAIL-918"},
        ],
        query="V2 demo cooking passphrase?",
        scope="personal",
    )

    assert [candidate.content for candidate in result.candidates] == [
        "V2 demo cooking passphrase is MISO-204"
    ]

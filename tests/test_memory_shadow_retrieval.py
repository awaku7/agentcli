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


def test_shadow_retrieval_prefers_phrase_tier_over_common_prefix_matches() -> None:
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
            item.reason == "weaker_match_tier" and item.action == "exclude"
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


def test_query_prefilter_never_skips_positive_lexical_relevance() -> None:
    from uagent.runtime.memory_retrieval import (
        _build_query_prefilter,
        _may_match_query_prefilter,
        _relevance,
    )

    queries = (
        "移行",
        "データベース移行",
        "V2演示料理口令是什么？",
        "V2เดโมรหัสอาหารคืออะไร?",
        "V2 demo cooking passphrase?",
        "src/uagent/runtime/session_store.py",
        "MCP4012",
        "new-1",
        "%_!",
        "first term" + chr(10) + "MCP4012",
        "",
        "   ",
    )
    notes = (
        "手順の移行作業",
        "データベース移行の安全策",
        "V2演示的料理口令是 MISO-204。",
        "V2เดโมรหัสอาหารคือ MISO-204",
        "V2 demo cooking passphrase is MISO-204",
        "edit src/uagent/runtime/session_store.py carefully",
        "MCP4012 is the retry identifier",
        "Use new-1 for the release",
        "literal %_! punctuation",
        "MCP4012 is the second-line match",
        "unrelated archived note",
        "",
    )

    for query in queries:
        prepared = _build_query_prefilter(query)
        for note in notes:
            if not _may_match_query_prefilter(note, prepared):
                assert _relevance(query, note) == 0.0, (query, note)


def test_prefilter_preserves_candidates_and_diagnostics(monkeypatch) -> None:
    from uagent.runtime import memory_retrieval

    records = [
        {"note": "データベース移行の安全策", "owner": "alice", "project": "app"},
        {"note": "移行作業のチェック項目", "owner": "alice", "project": "app"},
        {"note": "V2演示的料理口令是 MISO-204。", "owner": "alice", "project": "app"},
        {"note": "V2เดโมรหัสอาหารคือ MISO-204", "owner": "alice", "project": "app"},
        {
            "note": "V2 demo cooking passphrase is MISO-204",
            "owner": "alice",
            "project": "app",
        },
        {
            "note": "edit src/uagent/runtime/session_store.py carefully",
            "owner": "alice",
            "project": "app",
        },
        {"note": "MCP4012 is the retry identifier", "owner": "alice", "project": "app"},
        {"note": "new-1 is the release label", "owner": "alice", "project": "app"},
        {"note": "same duplicate phrase", "owner": "alice", "project": "app"},
        {"note": "same duplicate phrase", "owner": "alice", "project": "app"},
        {
            "scope": "shared",
            "note": "shared database rule",
            "owner": "alice",
            "project": "app",
        },
        {"note": "other owner database rule", "owner": "bob", "project": "app"},
        {"note": "other project database rule", "owner": "alice", "project": "web"},
        {"note": "legacy database note"},
        {"note": "", "owner": "alice", "project": "app"},
        "invalid record",
    ]
    cases = (
        ("移行", "personal", "alice", "app", True),
        ("V2演示料理口令是什么？", "personal", "alice", "app", True),
        ("V2เดโมรหัสอาหารคืออะไร?", "personal", "alice", "app", True),
        ("V2 demo cooking passphrase?", "personal", "alice", "app", True),
        ("src/uagent/runtime/session_store.py", "personal", "alice", "app", True),
        ("MCP4012", "personal", "alice", "app", True),
        ("new-1", "personal", "alice", "app", True),
        ("database", "personal", "alice", "app", False),
        (chr(10), "personal", "alice", "app", True),
    )

    optimized = [
        memory_retrieval.shadow_retrieve_memories(
            records,
            query=query,
            scope=scope,
            owner=owner,
            project=project,
            backend_revision="diff-test",
            allow_legacy_unknown=allow_legacy_unknown,
        )
        for query, scope, owner, project, allow_legacy_unknown in cases
    ]
    with monkeypatch.context() as patch:
        patch.setattr(
            memory_retrieval,
            "_may_match_query_prefilter",
            lambda _note, _prepared: True,
        )
        unfiltered = [
            memory_retrieval.shadow_retrieve_memories(
                records,
                query=query,
                scope=scope,
                owner=owner,
                project=project,
                backend_revision="diff-test",
                allow_legacy_unknown=allow_legacy_unknown,
            )
            for query, scope, owner, project, allow_legacy_unknown in cases
        ]

    for actual, reference in zip(optimized, unfiltered):
        assert actual.to_dict() == reference.to_dict()
        assert [
            (
                candidate.content,
                candidate.relevance,
                candidate.item_id,
                candidate.reference,
            )
            for candidate in actual.candidates
        ] == [
            (
                candidate.content,
                candidate.relevance,
                candidate.item_id,
                candidate.reference,
            )
            for candidate in reference.candidates
        ]

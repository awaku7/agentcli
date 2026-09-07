from uagent.runtime.context_retrieval import retrieve_candidates


def test_retrieve_candidates_ranks_query_match_and_returns_provider_neutral_items():
    records = [
        {
            "result_id": "unrelated",
            "summary": "weather report",
            "importance": "normal",
        },
        {
            "result_id": "matching",
            "summary": "database migration completed",
            "importance": "high",
            "artifact_preview": "migration details",
        },
    ]

    candidates = retrieve_candidates(records, query="database migration")

    assert [candidate.item_id for candidate in candidates] == [
        "matching",
        "unrelated",
    ]
    assert candidates[0].section == "tool_results"
    assert candidates[0].content == "migration details"


def test_retrieve_candidates_respects_limit():
    records = [{"result_id": str(index), "summary": "item"} for index in range(3)]

    assert len(retrieve_candidates(records, max_candidates=2)) == 2


def test_retrieve_candidates_uses_tool_name_and_artifact_preview_for_matching():
    records = [
        {
            "result_id": "tool-match",
            "tool_name": "database_query",
            "summary": "completed",
            "artifact_preview": "migration output",
        },
        {"result_id": "other", "summary": "unrelated"},
    ]

    candidates = retrieve_candidates(records, query="database migration")

    assert candidates[0].item_id == "tool-match"
    assert candidates[0].relevance == 0.5


def test_retrieve_candidates_supports_medium_importance_and_deterministic_ties():
    records = [
        {"result_id": "b", "summary": "same", "importance": "medium"},
        {"result_id": "a", "summary": "same", "importance": "normal"},
    ]

    candidates = retrieve_candidates(records, query="same")

    assert [candidate.item_id for candidate in candidates] == ["a", "b"]
    assert candidates[0].importance == 0.5


def test_retrieve_candidates_rejects_negative_limit():
    try:
        retrieve_candidates([], max_candidates=-1)
    except ValueError as exc:
        assert "max_candidates" in str(exc)
    else:
        raise AssertionError("negative max_candidates must be rejected")

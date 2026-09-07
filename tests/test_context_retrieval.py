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

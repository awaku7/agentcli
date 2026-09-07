from uagent.runtime.active_context import ContextCandidate
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


def test_context_candidate_from_record_normalizes_persisted_shape():
    candidate = ContextCandidate.from_record(
        {
            "result_id": "artifact-1",
            "summary": "summary",
            "artifact_ref": "artifacts/a.txt",
            "section": "artifacts",
        }
    )

    assert candidate.item_id == "artifact-1"
    assert candidate.section == "artifacts"
    assert candidate.content == "summary"
    assert candidate.reference == "artifacts/a.txt"


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


def test_retrieve_candidates_preserves_non_tool_context_metadata():
    candidates = retrieve_candidates(
        [
            {
                "item_id": "memory-1",
                "source": "memory",
                "section": "memory",
                "title": "deployment decision",
                "content": "use the blue deployment",
                "importance": "high",
                "relevance": 0.8,
                "recency": 0.9,
                "reference": "memory://deployment",
            }
        ],
        query="deployment",
    )

    assert candidates[0].item_id == "memory-1"
    assert candidates[0].source == "memory"
    assert candidates[0].section == "memory"
    assert candidates[0].content == "use the blue deployment"
    assert candidates[0].relevance == 0.8
    assert candidates[0].recency == 0.9
    assert candidates[0].reference == "memory://deployment"

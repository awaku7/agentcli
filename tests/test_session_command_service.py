from __future__ import annotations

from uagent.runtime.session_command_service import SessionCommandService


class _Store:
    def search(self, query, *, project=None):
        assert query == "needle"
        assert project == "demo"
        return [
            {
                "session_id": "s1",
                "created_at": "2025-01-02T00:00:00",
                "role": "user",
                "content": "first hit",
            },
            {
                "session_id": "s1",
                "created_at": "2025-01-03T00:00:00",
                "role": "assistant",
                "content": "second hit",
            },
            {
                "session_id": "s2",
                "created_at": "2025-02-01T00:00:00",
                "role": "user",
                "content": "other hit",
            },
        ]

    def list_sessions(self):
        return [
            {
                "session_id": "s1",
                "project": "demo",
                "message_count": 2,
                "summary": "summary 1",
            },
            {
                "session_id": "s2",
                "project": "demo",
                "message_count": 1,
                "summary": "summary 2",
            },
        ]


def test_search_projects_message_hits_into_sorted_session_rows() -> None:
    results = SessionCommandService(_Store()).search(
        "needle",
        project="demo",
    )

    assert [result.row["session_id"] for result in results] == ["s2", "s1"]
    assert results[0].matches == 1
    assert results[0].hit_role == "user"
    assert results[0].hit_content == "other hit"
    assert results[1].matches == 2
    assert results[1].row["summary"] == "summary 1"
    assert results[1].row["created_at"] == "2025-01-03T00:00:00"
    assert results[1].hit_role == "user"
    assert results[1].hit_content == "first hit"


def test_search_sort_keys_are_applied_by_service() -> None:
    results = SessionCommandService(_Store()).search(
        "needle",
        project="demo",
        sort_keys=("matches",),
    )

    assert [result.row["session_id"] for result in results] == ["s1", "s2"]

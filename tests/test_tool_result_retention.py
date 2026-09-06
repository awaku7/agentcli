from __future__ import annotations

from uagent.runtime.session_store import SessionStore


def test_prune_tool_results_keeps_newest_and_non_evictable(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        for result_id, evictable, created_at in (
            ("old", True, "2026-01-01T00:00:00+00:00"),
            ("new", True, "2026-01-02T00:00:00+00:00"),
            ("keep", False, "2026-01-03T00:00:00+00:00"),
        ):
            store.record_tool_result(
                session.session_id,
                {
                    "result_id": result_id,
                    "tool_name": "example",
                    "evictable": evictable,
                    "created_at": created_at,
                },
                result_id,
            )

        assert store.prune_tool_results(session.session_id, max_rows=1) == 1
        results = store.list_tool_results(session.session_id)

    assert {item["result_id"] for item in results} == {"new", "keep"}

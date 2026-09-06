from __future__ import annotations

from uagent.runtime.session_store import SessionStore


def test_tool_result_record_is_persisted_and_decoded(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "result-1",
                "task_id": "task-1",
                "tool_name": "example",
                "result_class": "large",
                "size_bytes": 123,
                "summary": "summary",
                "artifact_ref": "artifact://a1",
                "importance": "high",
                "evictable": False,
                "created_at": "2026-01-01T00:00:00+00:00",
                "metadata": {"tool_call_id": "call-1"},
            },
            {"role": "tool", "content": "bounded"},
        )

        results = store.list_tool_results(session.session_id)

    assert len(results) == 1
    assert results[0]["result_id"] == "result-1"
    assert results[0]["result_class"] == "large"
    assert results[0]["evictable"] is False
    assert results[0]["persistent_history"]["content"] == "bounded"
    assert results[0]["metadata"]["tool_call_id"] == "call-1"


def test_tool_result_session_lookup_by_task_id(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="a2a")
        store.record_tool_result(
            session.session_id,
            {"result_id": "task-result", "task_id": "task-1", "tool_name": "example"},
            "result",
        )

        assert store.find_sessions_by_task_id("task-1") == [session.session_id]
        assert store.find_sessions_by_task_id("missing") == []


def test_tool_result_can_be_retrieved_by_id(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {"result_id": "result-id", "tool_name": "read_file"},
            {"content": "full result"},
        )

        result = store.get_tool_result(session.session_id, "result-id")
        missing = store.get_tool_result(session.session_id, "missing")

    assert result is not None
    assert result["persistent_history"] == {"content": "full result"}
    assert missing is None


def test_tool_result_search_and_context_projection(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "result-search",
                "tool_name": "read_file",
                "summary": "configuration source",
                "artifact_ref": "artifact://cfg",
            },
            "configuration content",
        )

        results = store.search_tool_results(session.session_id, "configuration")

    assert len(results) == 1
    assert results[0]["result_id"] == "result-search"
    assert results[0]["persistent_history"] == "configuration content"


def test_tool_result_search_ranks_summary_and_supports_multiple_tokens(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {"result_id": "weak", "tool_name": "read_file", "summary": "source"},
            "configuration text",
        )
        store.record_tool_result(
            session.session_id,
            {
                "result_id": "strong",
                "tool_name": "configuration_reader",
                "summary": "configuration source",
            },
            "other",
        )

        results = store.search_tool_results(session.session_id, "configuration source")

    assert results[0]["result_id"] == "strong"


def test_tool_result_record_sanitizes_binary_history(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.record_tool_result(
            session.session_id,
            {"result_id": "result-2", "tool_name": "image"},
            {"image_b64": "secret", "path": "/tmp/image.png"},
        )
        result = store.list_tool_results(session.session_id)[0]

    assert "secret" not in str(result["persistent_history"])
    assert result["persistent_history"]["path"] == "/tmp/image.png"

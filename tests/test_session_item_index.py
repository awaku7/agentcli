from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from uagent.runtime.session_store import SessionStore, SessionStoreError


def _tool_call(call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": "read_file", "arguments": '{"filename":"a.txt"}'},
    }


def _tool_result_record(result_id: str, call_id: str) -> dict:
    return {
        "result_id": result_id,
        "tool_name": "read_file",
        "result_class": "small",
        "size_bytes": 4,
        "summary": "read complete",
        "artifact_ref": "",
        "importance": "normal",
        "evictable": True,
        "metadata": {"tool_call_id": call_id},
    }


def test_new_session_items_have_one_monotonic_sequence(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        assert store.get_session_item_watermark(session.session_id) == 0

        store.append_message(session.session_id, "user", "read a file")
        store.append_message(
            session.session_id,
            "assistant",
            "",
            payload={"role": "assistant", "tool_calls": [_tool_call("call-1")]},
        )
        store.record_tool_result(
            session.session_id,
            _tool_result_record("result-1", "call-1"),
            {"ok": True},
        )
        store.append_message(
            session.session_id,
            "tool",
            "read complete",
            payload={"role": "tool", "tool_call_id": "call-1"},
        )
        store.record_tool_call(
            session.session_id,
            tool_name="read_file",
            args={"filename": "a.txt"},
            result="read complete",
            status="success",
            call_id="call-1",
        )
        event_seq = store.record_session_item(
            session.session_id, "runtime_event", "event-1"
        )
        assert (
            store.record_session_item(session.session_id, "runtime_event", "event-1")
            == event_seq
        )

        items = store.list_session_items(
            session.session_id, start_seq=1, end_seq=event_seq
        )

    assert [
        (item["session_seq"], item["item_kind"], item["item_id"]) for item in items
    ] == [
        (1, "message", "1"),
        (2, "message", "2"),
        (3, "tool_call", "call-1"),
        (4, "tool_result", "result-1"),
        (5, "message", "3"),
        (6, "runtime_event", "event-1"),
    ]
    assert all(item["ordering_quality"] == "exact" for item in items)


def test_watermark_is_fixed_and_invalid_ranges_are_rejected(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.append_message(session.session_id, "user", "before")
        watermark = store.get_session_item_watermark(session.session_id)
        store.append_message(session.session_id, "user", "after")

        fixed = store.list_session_items(
            session.session_id, start_seq=1, end_seq=watermark
        )
        assert len(fixed) == 1
        with pytest.raises(SessionStoreError, match="exceeds the captured"):
            store.list_session_items(
                session.session_id, start_seq=1, end_seq=watermark + 2
            )
        with pytest.raises(ValueError, match="end_seq must be greater"):
            store.list_session_items(session.session_id, start_seq=2, end_seq=1)


def test_concurrent_session_appends_allocate_unique_monotonic_sequences(
    tmp_path,
) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    first_store = SessionStore(db_path)
    second_store = SessionStore(db_path)
    session = first_store.create_session(project="demo", entry_point="test")
    stores = (first_store, second_store)

    def append(index: int) -> int:
        return stores[index % len(stores)].append_message(
            session.session_id, "user", f"message-{index}"
        )

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(append, range(24)))
        items = first_store.list_session_items(
            session.session_id,
            start_seq=1,
            end_seq=first_store.get_session_item_watermark(session.session_id),
        )
    finally:
        first_store.close()
        second_store.close()

    assert [item["session_seq"] for item in items] == list(range(1, 25))
    assert len({item["item_id"] for item in items}) == 24


def test_legacy_backfill_preserves_message_order_and_marks_ambiguous_items(
    tmp_path,
) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    store = SessionStore(db_path)
    session = store.create_session(project="legacy", entry_point="test")
    call_payload = {"role": "assistant", "tool_calls": [_tool_call("call-legacy")]}
    tool_payload = {"role": "tool", "tool_call_id": "call-legacy"}
    store._execute(
        "INSERT INTO messages(message_id, session_id, role, content, payload_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (101, session.session_id, "user", "request", None),
    )
    store._execute(
        "INSERT INTO messages(message_id, session_id, role, content, payload_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            102,
            session.session_id,
            "assistant",
            "",
            json.dumps(call_payload),
        ),
    )
    store._execute(
        "INSERT INTO messages(message_id, session_id, role, content, payload_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            103,
            session.session_id,
            "tool",
            "read complete",
            json.dumps(tool_payload),
        ),
    )
    store._execute(
        "INSERT INTO tool_calls(call_id, session_id, tool_name, args_json, result, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("call-legacy", session.session_id, "read_file", "{}", "ok", "success"),
    )
    store._execute(
        "INSERT INTO tool_calls(call_id, session_id, tool_name, args_json, result, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("call-orphan", session.session_id, "search", "{}", "ok", "success"),
    )
    for result_id, metadata in (
        ("result-linked", {"tool_call_id": "call-legacy"}),
        ("result-orphan", {}),
    ):
        store._execute(
            "INSERT INTO tool_results(result_id, session_id, tool_name, result_class, "
            "size_bytes, summary, artifact_ref, importance, evictable, metadata_json, "
            "persistent_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result_id,
                session.session_id,
                "tool",
                "small",
                10,
                "result",
                None,
                "normal",
                1,
                json.dumps(metadata),
                "{}",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    # Simulate an old store that predates the ordered source index.
    store._execute("DROP TABLE session_items")
    store.close()

    with SessionStore(db_path) as reopened:
        items = reopened.list_session_items(
            session.session_id,
            start_seq=1,
            end_seq=reopened.get_session_item_watermark(session.session_id),
            require_exact_order=False,
        )
        exact_prefix = reopened.list_session_items(
            session.session_id, start_seq=1, end_seq=5
        )
        with pytest.raises(SessionStoreError, match="ambiguous ordering"):
            reopened.list_session_items(
                session.session_id,
                start_seq=1,
                end_seq=reopened.get_session_item_watermark(session.session_id),
            )
        previous_watermark = reopened.get_session_item_watermark(session.session_id)
        reopened.append_message(session.session_id, "user", "new turn")
        new_items = reopened.list_session_items(
            session.session_id,
            start_seq=previous_watermark + 1,
            end_seq=reopened.get_session_item_watermark(session.session_id),
        )

    assert [(item["item_kind"], item["item_id"]) for item in exact_prefix] == [
        ("message", "101"),
        ("message", "102"),
        ("tool_call", "call-legacy"),
        ("tool_result", "result-linked"),
        ("message", "103"),
    ]
    assert all(
        item["ordering_quality"] == "legacy_message_order" for item in exact_prefix
    )
    assert any(item["ordering_quality"] == "legacy_approximate" for item in items)
    assert len(new_items) == 1
    assert new_items[0]["ordering_quality"] == "exact"


def test_pruned_tool_result_keeps_unavailable_sequence_tombstone(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        first = _tool_result_record("result-old", "call-old")
        first["created_at"] = "2020-01-01T00:00:00+00:00"
        second = _tool_result_record("result-new", "call-new")
        second["created_at"] = "2021-01-01T00:00:00+00:00"
        store.record_tool_result(session.session_id, first, {"old": True})
        store.record_tool_result(session.session_id, second, {"new": True})

        assert store.prune_tool_results(session.session_id, max_rows=1) == 1
        items = store.list_session_items(
            session.session_id,
            start_seq=1,
            end_seq=store.get_session_item_watermark(session.session_id),
            require_available=False,
        )

    assert [item["availability"] for item in items] == ["unavailable", "available"]
    assert items[0]["item_id"] == "result-old"
    assert items[1]["item_id"] == "result-new"


def test_replacing_messages_tombstones_old_sequence_entries(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="demo", entry_point="test")
        store.append_message(session.session_id, "user", "old")
        store.replace_messages(session.session_id, [{"role": "user", "content": "new"}])
        watermark = store.get_session_item_watermark(session.session_id)
        with pytest.raises(SessionStoreError, match="unavailable items"):
            store.list_session_items(session.session_id, start_seq=1, end_seq=watermark)
        items = store.list_session_items(
            session.session_id,
            start_seq=1,
            end_seq=watermark,
            require_available=False,
        )

    assert items[0]["availability"] == "unavailable"
    assert items[1]["availability"] == "available"
    assert items[1]["session_seq"] > items[0]["session_seq"]

from __future__ import annotations

import json
from typing import Any

import pytest

from uagent.runtime import memory_store
from uagent.tools import long_memory
from uagent.tools import search_past_sessions_tool as tool
from uagent.tools.context import ToolCallbacks, init_callbacks

_REAL_STRICT = long_memory.forgotten_note_keys_strict


@pytest.fixture(autouse=True)
def _no_forgotten(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(long_memory, "forgotten_note_keys_strict", lambda: set())


class _FakeStore:
    def __init__(self, hits: list[dict[str, Any]]) -> None:
        self.hits = hits

    def search(
        self, query: str, *, project: Any = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        return [
            dict(hit) for hit in self.hits if query in str(hit.get("content") or "")
        ][:limit]


def _hit(
    session_id: str,
    content: str,
    *,
    role: str = "user",
    created_at: str = "2026-11-10 10:00:00",
    entry_point: str = "cli",
    project: str = "app",
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "project": project,
        "entry_point": entry_point,
        "role": role,
        "content": content,
        "created_at": created_at,
    }


def _run(
    store: Any, args: dict[str, Any], *, session_id: str = "active"
) -> dict[str, Any]:
    init_callbacks(ToolCallbacks(session_id=session_id, session_store=store))
    try:
        return json.loads(tool.run_tool(args))
    finally:
        init_callbacks(ToolCallbacks())


def test_returns_grouped_excerpts_newest_first() -> None:
    store = _FakeStore(
        [
            _hit("old", "合言葉はバナナにした", created_at="2026-11-08 09:00:00"),
            _hit(
                "new",
                "合言葉の件は決着した",
                role="assistant",
                created_at="2026-11-12 09:00:00",
            ),
            _hit("new", "合言葉を再確認した", created_at="2026-11-12 09:05:00"),
        ]
    )
    result = _run(store, {"query": "合言葉"})
    assert result["ok"] is True
    assert [s["session_id"] for s in result["sessions"]] == ["new", "old"]
    assert result["sessions"][0]["matches"] == 2
    assert result["sessions"][0]["excerpts"][0]["role"] == "assistant"


def test_excludes_active_subagent_and_hidden_roles() -> None:
    store = _FakeStore(
        [
            _hit("active", "合言葉の話"),
            _hit("sub", "合言葉の話", entry_point="sub-agent"),
            _hit("past", "合言葉の話", role="system"),
            _hit("past", "合言葉の話", role="tool"),
            _hit("past", "合言葉の話", role="assistant"),
        ]
    )
    result = _run(store, {"query": "合言葉"})
    assert [s["session_id"] for s in result["sessions"]] == ["past"]
    assert result["sessions"][0]["matches"] == 1


def test_forget_screening_drops_restated_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forgotten = long_memory.note_key_for("合言葉はバナナ")
    monkeypatch.setattr(long_memory, "forgotten_note_keys_strict", lambda: {forgotten})
    store = _FakeStore(
        [
            _hit("tainted", "前に決めた合言葉はバナナにしたよ"),
            _hit("clean", "合言葉の件は来週確認する"),
        ]
    )
    result = _run(store, {"query": "合言葉"})
    assert [s["session_id"] for s in result["sessions"]] == ["clean"]


def test_degenerate_forgotten_keys_do_not_block_everything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A punctuation-only note normalizes to an empty key, and a very
    # short key appears inside unrelated text; neither may withhold
    # every hit.
    monkeypatch.setattr(long_memory, "forgotten_note_keys_strict", lambda: {"", "あ"})
    store = _FakeStore([_hit("past", "合言葉の話をした")])
    result = _run(store, {"query": "合言葉"})
    assert [s["session_id"] for s in result["sessions"]] == ["past"]


def test_unreadable_memory_store_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The lenient forgotten_note_keys() swallows read errors and
    # returns an empty set; the tool must use the strict reader so a
    # broken memory store cannot pass forgotten content through.
    monkeypatch.setattr(long_memory, "forgotten_note_keys_strict", _REAL_STRICT)

    def _raise(path: Any) -> Any:
        raise OSError("memory store unreadable")

    monkeypatch.setattr(memory_store, "open_memory_store", _raise)
    store = _FakeStore([_hit("past", "合言葉の話をした")])
    result = _run(store, {"query": "合言葉"})
    assert result == {"ok": False, "error": "forget_screening_unavailable"}


def test_non_local_turn_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "current_turn_is_local", lambda: False)
    result = _run(_FakeStore([_hit("past", "合言葉の話")]), {"query": "合言葉"})
    assert result == {"ok": False, "error": "local_sessions_only"}


def test_missing_store_is_an_error_result() -> None:
    result = _run(None, {"query": "合言葉"})
    assert result == {"ok": False, "error": "session_store_unavailable"}


def test_empty_query_and_invalid_limit() -> None:
    store = _FakeStore([])
    assert _run(store, {"query": "  "}) == {"ok": False, "error": "query_empty"}
    assert _run(store, {"query": "x", "limit": 0}) == {
        "ok": False,
        "error": "invalid_limit",
    }
    assert _run(store, {"query": "x", "limit": "many"}) == {
        "ok": False,
        "error": "invalid_limit",
    }


def test_newest_session_is_not_cut_off_by_older_hits() -> None:
    # The store returns hits oldest first; a busy old session must not
    # push the newest matching session out of the fetch window.
    hits = [
        _hit("old", f"合言葉その{i}", created_at="2026-11-01 10:00:00")
        for i in range(250)
    ]
    hits.append(_hit("new", "合言葉の最終確認", created_at="2026-11-14 10:00:00"))
    result = _run(_FakeStore(hits), {"query": "合言葉"})
    assert result["sessions"][0]["session_id"] == "new"
    assert result["truncated"] is False


def test_saturated_window_reports_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tool, "_SEARCH_WINDOW", 5)
    hits = [_hit(f"s{i}", "合言葉の話") for i in range(10)]
    result = _run(_FakeStore(hits), {"query": "合言葉"})
    assert result["truncated"] is True


def test_excerpts_keep_the_latest_matches() -> None:
    store = _FakeStore(
        [
            _hit("past", f"合言葉メモ{i}", created_at=f"2026-11-10 10:0{i}:00")
            for i in range(5)
        ]
    )
    result = _run(store, {"query": "合言葉"})
    texts = [e["text"] for e in result["sessions"][0]["excerpts"]]
    assert texts == ["合言葉メモ2", "合言葉メモ3", "合言葉メモ4"]


def test_real_store_round_trip(repo_tmp_path: Any) -> None:
    from uagent.runtime.session_store import SessionStore

    with SessionStore(repo_tmp_path / "sessions.sqlite3") as store:
        active = store.create_session(project="app", entry_point="cli")
        past = store.create_session(project="app", entry_point="cli")
        store.append_message(past.session_id, "user", "合言葉はバナナに決めた")
        store.append_message(
            past.session_id, "assistant", "了解、合言葉はバナナで記録した"
        )
        store.append_message(active.session_id, "user", "合言葉の確認")
        result = _run(store, {"query": "合言葉"}, session_id=active.session_id)

    assert [s["session_id"] for s in result["sessions"]] == [past.session_id]
    assert result["sessions"][0]["matches"] == 2
    assert result["sessions"][0]["project"] == "app"


def test_limit_caps_sessions_and_excerpts_are_clipped() -> None:
    store = _FakeStore(
        [
            _hit(
                f"s{index}",
                "合言葉 " + "あ" * 300,
                created_at=f"2026-11-{10 + index:02d} 10:00:00",
            )
            for index in range(4)
        ]
    )
    result = _run(store, {"query": "合言葉", "limit": 2})
    assert len(result["sessions"]) == 2
    text = result["sessions"][0]["excerpts"][0]["text"]
    assert len(text) == 200
    assert text.endswith("…")

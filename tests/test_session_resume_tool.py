from __future__ import annotations

import json
from queue import Queue

from uagent.tools.context import ToolCallbacks, init_callbacks
from uagent.tools.i18n_helper import make_tool_translator
from uagent.tools import session_resume_tool


HOST_LOCALES = (
    "ar",
    "bn",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fa",
    "fi",
    "fil",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "mn",
    "mr",
    "ms",
    "nb",
    "nl",
    "nn",
    "pl",
    "pt",
    "pt_BR",
    "ro",
    "ru",
    "sv",
    "sw",
    "th",
    "tr",
    "uk",
    "vi",
    "zh_CN",
    "zh_TW",
)


class _FakeStore:
    def __init__(self, rows, topic_hits=None):
        self.rows = [dict(row) for row in rows]
        self.topic_hits = {
            str(key): set(value) for key, value in (topic_hits or {}).items()
        }

    def get_session(self, session_id):
        return next(row for row in self.rows if row["session_id"] == session_id)

    def list_sessions(self, *, project=None, exclude_session_id=None):
        rows = self.rows
        if project is not None:
            rows = [row for row in rows if row.get("project") == project]
        if exclude_session_id is not None:
            rows = [
                row for row in rows if row.get("session_id") != exclude_session_id
            ]
        return [dict(row) for row in rows]

    def search(self, query, *, project=None):
        ids = self.topic_hits.get(str(query), set())
        output = []
        for row in self.rows:
            if row["session_id"] not in ids:
                continue
            if project is not None and row.get("project") != project:
                continue
            output.append(
                {
                    "session_id": row["session_id"],
                    "role": "user",
                    "content": str(query),
                    "created_at": row["created_at"],
                }
            )
        return output


def _run_with_callbacks(store, queue, args):
    init_callbacks(
        ToolCallbacks(
            session_id="active",
            session_store=store,
            event_queue=queue,
        )
    )
    try:
        return json.loads(session_resume_tool.run_tool(args))
    finally:
        init_callbacks(ToolCallbacks())


def test_latest_prefers_current_project_and_queues_load_command():
    store = _FakeStore(
        [
            {
                "session_id": "active",
                "project": "app",
                "created_at": "2026-09-22 02:00:00",
            },
            {
                "session_id": "app-previous",
                "project": "app",
                "created_at": "2026-09-21 03:00:00",
            },
            {
                "session_id": "other-newer",
                "project": "other",
                "created_at": "2026-09-22 01:00:00",
            },
        ]
    )
    queue = Queue()
    result = _run_with_callbacks(store, queue, {"when": "latest"})

    assert result["ok"] is True
    assert result["session_id"] == "app-previous"
    event = queue.get_nowait()
    assert event == {
        "kind": "command",
        "text": ":sessions load app-previous",
        "src": "session_resume",
    }


def test_topic_can_fall_back_to_another_project():
    store = _FakeStore(
        [
            {
                "session_id": "active",
                "project": "app",
                "created_at": "2026-09-22 02:00:00",
            },
            {
                "session_id": "app-previous",
                "project": "app",
                "created_at": "2026-09-20 03:00:00",
            },
            {
                "session_id": "excel-session",
                "project": "excel",
                "created_at": "2026-09-21 03:00:00",
            },
        ],
        topic_hits={"excel": {"excel-session"}},
    )
    queue = Queue()
    result = _run_with_callbacks(
        store,
        queue,
        {"when": "latest", "topic": "excel"},
    )

    assert result["ok"] is True
    assert result["session_id"] == "excel-session"
    assert queue.get_nowait()["text"] == ":sessions load excel-session"


def test_invalid_when_returns_structured_error_without_queueing():
    store = _FakeStore([])
    queue = Queue()
    result = _run_with_callbacks(store, queue, {"when": "tomorrow"})

    assert result == {
        "allowed": ["latest", "recent", "yesterday"],
        "error": "invalid_when",
        "ok": False,
    }
    assert queue.empty()


def test_missing_topic_match_does_not_resume_unrelated_session():
    store = _FakeStore(
        [
            {
                "session_id": "active",
                "project": "app",
                "created_at": "2026-09-22 02:00:00",
            },
            {
                "session_id": "previous",
                "project": "app",
                "created_at": "2026-09-21 03:00:00",
            },
        ]
    )
    queue = Queue()
    result = _run_with_callbacks(
        store,
        queue,
        {"when": "latest", "topic": "does-not-exist"},
    )

    assert result["ok"] is False
    assert result["error"] == "no_matching_session"
    assert queue.empty()


def test_tool_catalog_has_safe_fallback_for_all_host_locales(monkeypatch):
    translator = make_tool_translator(session_resume_tool.__file__)
    for locale in HOST_LOCALES:
        monkeypatch.setenv("UAGENT_LANG", locale)
        description = translator("tool.description", default="fallback")
        search_terms = translator("x_search_terms", default=["fallback"])
        assert isinstance(description, str) and description
        assert isinstance(search_terms, list) and search_terms


def test_representative_non_english_tool_catalogs_are_localized(monkeypatch):
    translator = make_tool_translator(session_resume_tool.__file__)
    values = {}
    for locale in ("ja", "zh_CN", "zh_TW", "th"):
        monkeypatch.setenv("UAGENT_LANG", locale)
        values[locale] = translator("tool.description", default="fallback")
    assert all(value != "fallback" for value in values.values())
    assert len(set(values.values())) == 4

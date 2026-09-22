from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue

from uagent.tools import session_resume_tool
from uagent.tools.context import ToolCallbacks, init_callbacks

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

REQUIRED_CATALOG_KEYS = {
    "tool.description",
    "x_search_terms",
    "param.when.description",
    "param.day_offset.description",
    "param.week_offset.description",
    "param.date_start.description",
    "param.date_end.description",
    "param.topic.description",
    "param.project.description",
    "param.session_id.description",
}


class _Store:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]

    def get_session(self, session_id):
        return next(row for row in self.rows if row["session_id"] == session_id)

    def list_sessions(self, *, project=None, exclude_session_id=None):
        rows = self.rows
        if project is not None:
            rows = [row for row in rows if row.get("project") == project]
        if exclude_session_id is not None:
            rows = [row for row in rows if row.get("session_id") != exclude_session_id]
        return [dict(row) for row in rows]

    def search(self, query, *, project=None):
        return []


def _run(rows, args):
    queue = Queue()
    init_callbacks(
        ToolCallbacks(
            session_id="active",
            session_store=_Store(rows),
            event_queue=queue,
        )
    )
    try:
        return json.loads(session_resume_tool.run_tool(args)), queue
    finally:
        init_callbacks(ToolCallbacks())


def test_tool_exposes_language_neutral_relative_time_fields():
    properties = session_resume_tool.TOOL_SPEC["function"]["parameters"]["properties"]
    assert properties["day_offset"]["minimum"] == 0
    assert properties["week_offset"]["minimum"] == 0
    assert "date_start" in properties
    assert "date_end" in properties


def test_day_offset_can_return_ambiguous_candidates():
    local_now = datetime.now().astimezone()
    target_date = local_now.date() - timedelta(days=2)
    target_noon = datetime.combine(
        target_date,
        datetime.min.time().replace(hour=12),
        tzinfo=local_now.tzinfo,
    )
    rows = [
        {
            "session_id": "active",
            "project": "app",
            "created_at": local_now.isoformat(),
        },
        {
            "session_id": "a",
            "project": "app",
            "created_at": target_noon.isoformat(),
        },
        {
            "session_id": "b",
            "project": "app",
            "created_at": (target_noon - timedelta(hours=2)).isoformat(),
        },
    ]
    result, queue = _run(rows, {"day_offset": 2})
    assert result["ok"] is True
    assert result["status"] == "ambiguous"
    assert result["day_offset"] == 2
    assert [item["session_id"] for item in result["candidates"]] == ["a", "b"]
    assert queue.empty()


def test_conflicting_time_selectors_are_rejected():
    result, queue = _run([], {"when": "recent", "week_offset": 1})
    assert result == {"error": "conflicting_time_selectors", "ok": False}
    assert queue.empty()


def test_partial_explicit_date_range_is_rejected():
    result, queue = _run([], {"date_start": "2026-09-14"})
    assert result == {"error": "incomplete_date_range", "ok": False}
    assert queue.empty()


def test_malformed_explicit_date_range_is_rejected():
    result, queue = _run(
        [],
        {"date_start": "2026-09-xx", "date_end": "2026-09-20"},
    )
    assert result == {"error": "invalid_date_range", "ok": False}
    assert queue.empty()


def test_reversed_explicit_date_range_is_rejected():
    result, queue = _run(
        [],
        {"date_start": "2026-09-20", "date_end": "2026-09-14"},
    )
    assert result == {"error": "invalid_date_range", "ok": False}
    assert queue.empty()


def test_all_host_locales_are_explicitly_translated_without_fallback():
    catalog_path = Path(session_resume_tool.__file__).with_suffix(".json")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    assert set(catalog) == set(HOST_LOCALES)
    english_description = catalog["en"]["tool.description"]
    for locale in HOST_LOCALES:
        entry = catalog[locale]
        assert REQUIRED_CATALOG_KEYS <= set(entry)
        assert isinstance(entry["x_search_terms"], list)
        assert len(entry["x_search_terms"]) >= 8
        if locale != "en":
            assert entry["tool.description"] != english_description


def test_every_locale_has_day_before_yesterday_and_last_week_search_terms():
    catalog_path = Path(session_resume_tool.__file__).with_suffix(".json")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    for locale in HOST_LOCALES:
        terms = catalog[locale]["x_search_terms"]
        assert len(terms) >= 8
        assert terms[4]
        assert terms[5]

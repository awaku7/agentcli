from __future__ import annotations

from datetime import datetime, timedelta, timezone

from uagent.runtime.session_resume import (
    SessionResumeRequest,
    select_session_resume_candidate,
)


def test_select_yesterday_uses_callers_local_calendar_and_newest_match():
    jst = timezone(timedelta(hours=9))
    now = datetime(2026, 9, 22, 13, 0, tzinfo=jst)
    sessions = [
        {"session_id": "today", "created_at": "2026-09-22 01:00:00"},
        {"session_id": "yesterday-new", "created_at": "2026-09-21 12:00:00"},
        {"session_id": "yesterday-old", "created_at": "2026-09-20 23:30:00"},
        {"session_id": "older", "created_at": "2026-09-20 10:00:00"},
    ]
    candidate = select_session_resume_candidate(
        sessions,
        SessionResumeRequest(when="yesterday"),
        now=now,
    )
    assert candidate is not None
    assert candidate.session_id == "yesterday-new"


def test_select_recent_is_bounded_and_can_intersect_topic_matches():
    now = datetime(2026, 9, 22, 4, 0, tzinfo=timezone.utc)
    sessions = [
        {"session_id": "wanted", "created_at": "2026-09-22 03:00:00"},
        {"session_id": "newer-other", "created_at": "2026-09-22 03:30:00"},
        {"session_id": "too-old", "created_at": "2026-09-21 20:00:00"},
    ]
    candidate = select_session_resume_candidate(
        sessions,
        SessionResumeRequest(when="recent", topic="memory"),
        now=now,
        matching_session_ids={"wanted"},
    )
    assert candidate is not None
    assert candidate.session_id == "wanted"


def test_select_latest_ignores_future_rows():
    now = datetime(2026, 9, 22, 4, 0, tzinfo=timezone.utc)
    sessions = [
        {"session_id": "future", "created_at": "2026-09-22 05:00:00"},
        {"session_id": "latest", "created_at": "2026-09-22 03:30:00"},
        {"session_id": "older", "created_at": "2026-09-21 20:00:00"},
    ]
    candidate = select_session_resume_candidate(
        sessions,
        SessionResumeRequest(when="latest"),
        now=now,
    )
    assert candidate is not None
    assert candidate.session_id == "latest"


def test_unknown_window_matches_nothing():
    candidate = select_session_resume_candidate(
        [{"session_id": "s1", "created_at": "2026-09-22 03:00:00"}],
        SessionResumeRequest(when="tomorrow"),
        now=datetime(2026, 9, 22, 4, 0, tzinfo=timezone.utc),
    )
    assert candidate is None

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from uagent.runtime.session_resume import (
    SessionResumeRequest,
    list_session_resume_candidates,
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


def test_list_yesterday_candidates_preserves_metadata_and_order():
    jst = timezone(timedelta(hours=9))
    now = datetime(2026, 9, 22, 13, 0, tzinfo=jst)
    sessions = [
        {
            "session_id": "morning",
            "project": "agentcli",
            "created_at": "2026-09-21 00:30:00",
            "first_message": "Memory work",
            "last_message": "Merged PR",
            "summary": "Memory V2",
        },
        {
            "session_id": "evening",
            "project": "agentcli",
            "created_at": "2026-09-21 10:30:00",
            "first_message": "Weather",
            "last_message": "Weather",
            "summary": "Weather check",
        },
    ]

    candidates = list_session_resume_candidates(
        sessions,
        SessionResumeRequest(when="yesterday"),
        now=now,
    )

    assert [item.session_id for item in candidates] == ["evening", "morning"]
    assert candidates[1].project == "agentcli"
    assert candidates[1].summary == "Memory V2"
    assert candidates[1].first_message == "Memory work"


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


def test_day_offset_two_means_day_before_yesterday_in_local_calendar():
    jst = timezone(timedelta(hours=9))
    now = datetime(2026, 9, 22, 18, 0, tzinfo=jst)
    sessions = [
        {"session_id": "target", "created_at": "2026-09-20 03:00:00"},
        {"session_id": "yesterday", "created_at": "2026-09-21 03:00:00"},
        {"session_id": "older", "created_at": "2026-09-19 03:00:00"},
    ]

    candidate = select_session_resume_candidate(
        sessions,
        SessionResumeRequest(day_offset=2),
        now=now,
    )

    assert candidate is not None
    assert candidate.session_id == "target"


def test_week_offset_one_uses_previous_local_monday_to_sunday():
    jst = timezone(timedelta(hours=9))
    now = datetime(2026, 9, 22, 18, 0, tzinfo=jst)  # Tuesday
    sessions = [
        {"session_id": "sun", "created_at": "2026-09-20 10:00:00"},
        {"session_id": "mon", "created_at": "2026-09-14 10:00:00"},
        {"session_id": "before", "created_at": "2026-09-13 10:00:00"},
        {"session_id": "this-week", "created_at": "2026-09-21 10:00:00"},
    ]

    candidates = list_session_resume_candidates(
        sessions,
        SessionResumeRequest(week_offset=1),
        now=now,
    )

    assert [candidate.session_id for candidate in candidates] == ["sun", "mon"]


def test_explicit_local_date_range_is_inclusive():
    jst = timezone(timedelta(hours=9))
    now = datetime(2026, 9, 22, 18, 0, tzinfo=jst)
    sessions = [
        {"session_id": "end", "created_at": "2026-09-18 12:00:00"},
        {"session_id": "start", "created_at": "2026-09-16 00:00:00"},
        {"session_id": "outside", "created_at": "2026-09-15 00:00:00"},
    ]

    candidates = list_session_resume_candidates(
        sessions,
        SessionResumeRequest(date_start="2026-09-16", date_end="2026-09-18"),
        now=now,
    )

    assert [candidate.session_id for candidate in candidates] == ["end", "start"]


def test_invalid_date_range_matches_nothing():
    candidate = select_session_resume_candidate(
        [{"session_id": "s1", "created_at": "2026-09-20 03:00:00"}],
        SessionResumeRequest(date_start="2026-09-21", date_end="2026-09-20"),
        now=datetime(2026, 9, 22, 4, 0, tzinfo=timezone.utc),
    )
    assert candidate is None


def test_unknown_window_matches_nothing():
    candidate = select_session_resume_candidate(
        [{"session_id": "s1", "created_at": "2026-09-22 03:00:00"}],
        SessionResumeRequest(when="tomorrow"),
        now=datetime(2026, 9, 22, 4, 0, tzinfo=timezone.utc),
    )
    assert candidate is None

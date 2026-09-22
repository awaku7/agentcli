from __future__ import annotations

from datetime import datetime, timedelta, timezone

from uagent.runtime.session_resume import (
    SessionResumeIntent,
    parse_session_resume_intent,
    select_session_resume_candidate,
    supported_session_resume_locales,
)


EXPECTED_HOST_LOCALES = {
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
}


def test_resume_alias_catalog_covers_host_release_locales():
    assert set(supported_session_resume_locales()) == EXPECTED_HOST_LOCALES


def test_parse_japanese_yesterday_resume_without_topic():
    intent = parse_session_resume_intent("昨日の作業を再開")
    assert intent == SessionResumeIntent(window="yesterday", topic="", language="ja")


def test_parse_japanese_recent_resume_without_topic():
    intent = parse_session_resume_intent("さきほどの作業を再開")
    assert intent == SessionResumeIntent(window="recent", topic="", language="ja")


def test_parse_japanese_resume_keeps_meaningful_topic():
    intent = parse_session_resume_intent("昨日のUAG Memoryの作業を再開")
    assert intent == SessionResumeIntent(
        window="yesterday", topic="uag memory", language="ja"
    )


def test_parse_representative_multilingual_resume_phrases():
    assert parse_session_resume_intent("resume yesterday work") == SessionResumeIntent(
        window="yesterday", topic="", language="en"
    )
    assert parse_session_resume_intent("继续昨天的工作") == SessionResumeIntent(
        window="yesterday", topic="", language="zh_CN"
    )
    assert parse_session_resume_intent("เมื่อวานงานทำต่อ") == SessionResumeIntent(
        window="yesterday", topic="", language="th"
    )


def test_parser_does_not_steal_non_resume_chat():
    assert parse_session_resume_intent("昨日の作業について教えて") is None
    assert parse_session_resume_intent("再開方法を教えて") is None


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
        SessionResumeIntent(window="yesterday"),
        now=now,
    )
    assert candidate is not None
    assert candidate.session_id == "yesterday-new"


def test_select_recent_is_bounded_and_can_intersect_topic_matches():
    utc = timezone.utc
    now = datetime(2026, 9, 22, 4, 0, tzinfo=utc)
    sessions = [
        {"session_id": "wanted", "created_at": "2026-09-22 03:00:00"},
        {"session_id": "newer-other", "created_at": "2026-09-22 03:30:00"},
        {"session_id": "too-old", "created_at": "2026-09-21 20:00:00"},
    ]
    candidate = select_session_resume_candidate(
        sessions,
        SessionResumeIntent(window="recent", topic="memory"),
        now=now,
        matching_session_ids={"wanted"},
    )
    assert candidate is not None
    assert candidate.session_id == "wanted"

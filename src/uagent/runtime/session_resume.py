from __future__ import annotations

"""Language-neutral selection helpers for natural session resume.

Natural-language interpretation belongs to the LLM/tool layer. This module
only applies deterministic time/topic constraints to stored sessions.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class SessionResumeRequest:
    when: str = ""
    topic: str = ""
    project: str = ""
    day_offset: int | None = None
    week_offset: int | None = None
    date_start: str = ""
    date_end: str = ""


@dataclass(frozen=True)
class SessionResumeCandidate:
    session_id: str
    created_at: str
    project: str = ""
    first_message: str = ""
    last_message: str = ""
    summary: str = ""


def _parse_created_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    # SessionStore stores SQLite UTC timestamps without an explicit offset.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_local_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _date_window(
    request: SessionResumeRequest,
    local_now: datetime,
) -> tuple[date, date] | None:
    if request.date_start or request.date_end:
        start = _parse_local_date(request.date_start)
        end = _parse_local_date(request.date_end)
        if start is None or end is None or start > end:
            return None
        return start, end

    if request.day_offset is not None:
        if request.day_offset < 0:
            return None
        target = local_now.date() - timedelta(days=request.day_offset)
        return target, target

    if request.week_offset is not None:
        if request.week_offset < 0:
            return None
        # Deterministic ISO-style local week: Monday through Sunday.
        this_monday = local_now.date() - timedelta(days=local_now.weekday())
        start = this_monday - timedelta(weeks=request.week_offset)
        return start, start + timedelta(days=6)

    if request.when == "yesterday":
        target = local_now.date() - timedelta(days=1)
        return target, target

    return None


def _session_in_window(
    created_at: datetime,
    request: SessionResumeRequest,
    local_now: datetime,
) -> bool:
    local_created = created_at.astimezone(local_now.tzinfo)
    if request.when == "latest" and not any(
        (
            request.day_offset is not None,
            request.week_offset is not None,
            request.date_start,
            request.date_end,
        )
    ):
        return created_at <= local_now.astimezone(timezone.utc)
    if request.when == "recent" and not any(
        (
            request.day_offset is not None,
            request.week_offset is not None,
            request.date_start,
            request.date_end,
        )
    ):
        age = local_now - local_created
        return timedelta(0) <= age <= timedelta(hours=6)

    window = _date_window(request, local_now)
    if window is None:
        return False
    start, end = window
    return start <= local_created.date() <= end


def list_session_resume_candidates(
    sessions: Iterable[dict[str, Any]],
    request: SessionResumeRequest,
    *,
    now: datetime | None = None,
    matching_session_ids: set[str] | None = None,
) -> list[SessionResumeCandidate]:
    """Return matching sessions newest-first without resolving ambiguity."""

    local_now = now or datetime.now().astimezone()
    if local_now.tzinfo is None:
        local_now = local_now.astimezone()

    candidates: list[tuple[datetime, SessionResumeCandidate]] = []
    for row in sessions:
        session_id = str(row.get("session_id") or "")
        if not session_id:
            continue
        if matching_session_ids is not None and session_id not in matching_session_ids:
            continue
        created_at = _parse_created_at(row.get("created_at"))
        if created_at is None or not _session_in_window(created_at, request, local_now):
            continue
        candidates.append(
            (
                created_at,
                SessionResumeCandidate(
                    session_id=session_id,
                    created_at=str(row.get("created_at") or ""),
                    project=str(row.get("project") or ""),
                    first_message=str(row.get("first_message") or ""),
                    last_message=str(row.get("last_message") or ""),
                    summary=str(row.get("summary") or ""),
                ),
            )
        )

    candidates.sort(key=lambda item: (item[0], item[1].session_id), reverse=True)
    return [candidate for _, candidate in candidates]


def select_session_resume_candidate(
    sessions: Iterable[dict[str, Any]],
    request: SessionResumeRequest,
    *,
    now: datetime | None = None,
    matching_session_ids: set[str] | None = None,
) -> SessionResumeCandidate | None:
    """Select the newest matching session for backward-compatible callers."""

    candidates = list_session_resume_candidates(
        sessions,
        request,
        now=now,
        matching_session_ids=matching_session_ids,
    )
    return candidates[0] if candidates else None


__all__ = [
    "SessionResumeCandidate",
    "SessionResumeRequest",
    "list_session_resume_candidates",
    "select_session_resume_candidate",
]

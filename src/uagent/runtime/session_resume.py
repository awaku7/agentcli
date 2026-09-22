from __future__ import annotations

"""Language-neutral selection helpers for natural session resume.

Natural-language interpretation belongs to the LLM/tool layer.  This module
only applies deterministic time/topic constraints to stored sessions.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class SessionResumeRequest:
    when: str
    topic: str = ""
    project: str = ""


@dataclass(frozen=True)
class SessionResumeCandidate:
    session_id: str
    created_at: str


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


def _session_in_window(
    created_at: datetime,
    request: SessionResumeRequest,
    local_now: datetime,
) -> bool:
    local_created = created_at.astimezone(local_now.tzinfo)
    if request.when == "latest":
        return created_at <= local_now.astimezone(timezone.utc)
    if request.when == "yesterday":
        return local_created.date() == local_now.date() - timedelta(days=1)
    if request.when == "recent":
        age = local_now - local_created
        return timedelta(0) <= age <= timedelta(hours=6)
    return False


def select_session_resume_candidate(
    sessions: Iterable[dict[str, Any]],
    request: SessionResumeRequest,
    *,
    now: datetime | None = None,
    matching_session_ids: set[str] | None = None,
) -> SessionResumeCandidate | None:
    """Select the newest session satisfying time and optional topic matches."""

    local_now = now or datetime.now().astimezone()
    if local_now.tzinfo is None:
        local_now = local_now.astimezone()

    candidates: list[tuple[datetime, str, str]] = []
    for row in sessions:
        session_id = str(row.get("session_id") or "")
        if not session_id:
            continue
        if matching_session_ids is not None and session_id not in matching_session_ids:
            continue
        created_at = _parse_created_at(row.get("created_at"))
        if created_at is None or not _session_in_window(created_at, request, local_now):
            continue
        candidates.append((created_at, session_id, str(row.get("created_at") or "")))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, session_id, created_text = candidates[0]
    return SessionResumeCandidate(session_id=session_id, created_at=created_text)


__all__ = [
    "SessionResumeCandidate",
    "SessionResumeRequest",
    "select_session_resume_candidate",
]

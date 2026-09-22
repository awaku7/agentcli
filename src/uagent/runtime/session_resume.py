from __future__ import annotations

"""Resolve conservative natural-language requests to resume stored sessions.

Input recognition is intentionally separate from host UI translation.  The
locale alias data is packaged under ``uagent/data``; user-facing output remains
owned by the existing gettext-backed session command handlers.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SessionResumeIntent:
    window: str
    topic: str = ""
    language: str = ""


@dataclass(frozen=True)
class SessionResumeCandidate:
    session_id: str
    created_at: str


@lru_cache(maxsize=1)
def _alias_catalog() -> dict[str, dict[str, tuple[str, ...]]]:
    path = Path(__file__).resolve().parents[1] / "data" / "session_resume_aliases.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    locales = raw.get("locales") if isinstance(raw, dict) else None
    if not isinstance(locales, dict):
        return {}
    output: dict[str, dict[str, tuple[str, ...]]] = {}
    for locale, groups in locales.items():
        if not isinstance(groups, dict):
            continue
        normalized_groups: dict[str, tuple[str, ...]] = {}
        for name in ("resume", "yesterday", "recent", "noise"):
            values = groups.get(name)
            if isinstance(values, list):
                normalized_groups[name] = tuple(
                    str(value) for value in values if str(value).strip()
                )
            else:
                normalized_groups[name] = ()
        if normalized_groups["resume"]:
            output[str(locale)] = normalized_groups
    return output


def clear_session_resume_cache() -> None:
    _alias_catalog.cache_clear()


def supported_session_resume_locales() -> tuple[str, ...]:
    return tuple(sorted(_alias_catalog()))


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = re.sub(r"[\s\u3000]+", " ", value)
    return value.strip()


def _contains(value: str, alias: str) -> bool:
    needle = _normalize(alias)
    if not needle:
        return False
    # ASCII-like single words need token boundaries so e.g. ``continue`` does
    # not match part of an identifier.  Languages without reliable whitespace
    # segmentation use substring matching, but only after both a resume verb
    # and a temporal cue are present.
    if re.fullmatch(r"[a-z0-9_+-]+", needle):
        return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", value) is not None
    return needle in value


def _strip_alias(value: str, alias: str) -> str:
    needle = _normalize(alias)
    if not needle:
        return value
    if re.fullmatch(r"[a-z0-9_+-]+", needle):
        return re.sub(rf"(?<!\w){re.escape(needle)}(?!\w)", " ", value)
    return value.replace(needle, " ")


def parse_session_resume_intent(text: str) -> SessionResumeIntent | None:
    """Return a structured resume intent or ``None`` when the text is unsafe.

    Recognition requires both a resume expression and one temporal expression.
    This deliberately avoids treating ordinary topic mentions as host commands.
    """

    value = _normalize(text)
    if not value:
        return None

    matches: list[tuple[int, str, str, tuple[str, ...]]] = []
    catalog = _alias_catalog()
    for language, groups in catalog.items():
        resume_hits = tuple(
            alias for alias in groups["resume"] if _contains(value, alias)
        )
        if not resume_hits:
            continue
        for window in ("yesterday", "recent"):
            time_hits = tuple(
                alias for alias in groups[window] if _contains(value, alias)
            )
            if not time_hits:
                continue
            aliases = resume_hits + time_hits
            explained = sum(len(_normalize(alias)) for alias in aliases)
            matches.append((explained, language, window, aliases))

    if not matches:
        return None

    best_score = max(row[0] for row in matches)
    best = [row for row in matches if row[0] == best_score]
    targets = {(row[1], row[2]) for row in best}
    if len(targets) != 1:
        return None

    _, language, window, aliases = best[0]
    topic = value
    for alias in sorted(aliases, key=lambda item: len(_normalize(item)), reverse=True):
        topic = _strip_alias(topic, alias)
    for noise in sorted(
        catalog.get(language, {}).get("noise", ()),
        key=lambda item: len(_normalize(item)),
        reverse=True,
    ):
        topic = _strip_alias(topic, noise)
    topic = re.sub(r"[\s\u3000]+", " ", topic)
    topic = re.sub(r"^[\W_]+|[\W_]+$", "", topic, flags=re.UNICODE).strip()
    return SessionResumeIntent(window=window, topic=topic, language=language)


def _parse_created_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    # SessionStore's SQLite timestamps are UTC and intentionally stored without
    # an offset.  Explicit offsets from imported stores are preserved.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _session_in_window(
    created_at: datetime,
    intent: SessionResumeIntent,
    local_now: datetime,
) -> bool:
    local_created = created_at.astimezone(local_now.tzinfo)
    if intent.window == "yesterday":
        return local_created.date() == local_now.date() - timedelta(days=1)
    if intent.window == "recent":
        age = local_now - local_created
        return timedelta(0) <= age <= timedelta(hours=6)
    return False


def select_session_resume_candidate(
    sessions: Iterable[dict[str, Any]],
    intent: SessionResumeIntent,
    *,
    now: datetime | None = None,
    matching_session_ids: set[str] | None = None,
) -> SessionResumeCandidate | None:
    """Select the newest session inside the resolved local-time window."""

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
        if created_at is None or not _session_in_window(created_at, intent, local_now):
            continue
        candidates.append(
            (created_at, session_id, str(row.get("created_at") or ""))
        )

    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, session_id, created_text = candidates[0]
    return SessionResumeCandidate(session_id=session_id, created_at=created_text)


__all__ = [
    "SessionResumeCandidate",
    "SessionResumeIntent",
    "clear_session_resume_cache",
    "parse_session_resume_intent",
    "select_session_resume_candidate",
    "supported_session_resume_locales",
]

from __future__ import annotations

import json
from typing import Any

from ..runtime.session_command_service import SessionCommandService
from ..runtime.session_resume import (
    SessionResumeCandidate,
    SessionResumeRequest,
    list_session_resume_candidates,
)
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "session_resume",
        "description": _(
            "tool.description",
            default=(
                "Resumes a stored UAG CLI session from natural-language requests such as "
                "'resume yesterday's work' or 'continue the work from a moment ago'. "
                "Interpret the user's language yourself and map the request to when=latest, "
                "recent, or yesterday. If the tool returns ambiguous candidates, ask the "
                "user which one they want and call again with that candidate's session_id."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "session resume",
                "resume previous session",
                "continue previous work",
                "yesterday work",
                "recent work",
                "previous conversation",
            ],
        ),
        "x_search_terms_en": [
            "session resume",
            "resume previous session",
            "continue previous work",
            "yesterday work",
            "recent work",
            "previous conversation",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "when": {
                    "type": "string",
                    "enum": ["latest", "recent", "yesterday"],
                    "description": _(
                        "param.when.description",
                        default=(
                            "Time selector. Use latest for the newest previous session, "
                            "recent for a session used within about six hours, or yesterday "
                            "for the user's local calendar day before today."
                        ),
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": _(
                        "param.topic.description",
                        default=(
                            "Optional topic keywords from the user's request, excluding words "
                            "that only mean resume, work, recent, or yesterday."
                        ),
                    ),
                },
                "project": {
                    "type": "string",
                    "description": _(
                        "param.project.description",
                        default=(
                            "Optional exact stored project name. Leave empty to prefer the "
                            "current project's sessions."
                        ),
                    ),
                },
                "session_id": {
                    "type": "string",
                    "description": _(
                        "param.session_id.description",
                        default=(
                            "Exact candidate session_id to resume after the user chooses from "
                            "an ambiguous result. When set, when/topic are not required."
                        ),
                    ),
                },
            },
            "required": [],
        },
    },
}


def _result(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _current_project(store: Any, active_session_id: str) -> str:
    if not active_session_id:
        return ""
    try:
        row = store.get_session(active_session_id)
    except Exception:
        return ""
    return str((row or {}).get("project") or "").strip()


def _matching_ids(
    service: SessionCommandService,
    topic: str,
    *,
    project: str | None,
) -> set[str] | None:
    if not topic:
        return None
    try:
        results = service.search(topic, project=project)
    except Exception:
        return set()
    return {
        str(result.row.get("session_id") or "")
        for result in results
        if str(result.row.get("session_id") or "")
    }


def _candidates(
    store: Any,
    request: SessionResumeRequest,
    *,
    active_session_id: str,
    project: str | None,
) -> list[SessionResumeCandidate]:
    try:
        sessions = store.list_sessions(
            project=project,
            exclude_session_id=active_session_id or None,
        )
    except TypeError:
        sessions = [
            row
            for row in store.list_sessions()
            if str(row.get("session_id") or "") != active_session_id
            and (project is None or str(row.get("project") or "") == project)
        ]
    service = SessionCommandService(store)
    matching_ids = _matching_ids(service, request.topic, project=project)
    return list_session_resume_candidates(
        sessions,
        request,
        matching_session_ids=matching_ids,
    )


def _clip(value: str, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _candidate_payload(candidate: SessionResumeCandidate, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "session_id": candidate.session_id,
        "created_at": candidate.created_at,
        "project": candidate.project,
        "summary": _clip(candidate.summary),
        "first_message": _clip(candidate.first_message),
        "last_message": _clip(candidate.last_message),
    }


def _queue_session(event_queue: Any, session_id: str) -> str:
    event_queue.put(
        {
            "kind": "command",
            "text": f":sessions load {session_id}",
            "src": "session_resume",
        }
    )
    return _result(
        ok=True,
        status="queued",
        control_transfer=True,
        session_id=session_id,
    )


def run_tool(args: dict[str, Any]) -> str:
    callbacks = get_callbacks()
    store = callbacks.session_store
    active_session_id = str(callbacks.session_id or "")
    event_queue = callbacks.event_queue

    if store is None:
        return _result(ok=False, error="session_store_unavailable")
    if event_queue is None or not callable(getattr(event_queue, "put", None)):
        return _result(ok=False, error="host_session_switch_unavailable")

    explicit_session_id = str(args.get("session_id") or "").strip()
    if explicit_session_id:
        if explicit_session_id == active_session_id:
            return _result(ok=False, error="session_already_active")
        try:
            store.get_session(explicit_session_id)
        except Exception:
            return _result(ok=False, error="unknown_session", session_id=explicit_session_id)
        return _queue_session(event_queue, explicit_session_id)

    when = str(args.get("when") or "").strip().lower()
    if when not in {"latest", "recent", "yesterday"}:
        return _result(
            ok=False,
            error="invalid_when",
            allowed=["latest", "recent", "yesterday"],
        )

    topic = str(args.get("topic") or "").strip()
    explicit_project = str(args.get("project") or "").strip()
    inferred_project = explicit_project or _current_project(store, active_session_id)
    request = SessionResumeRequest(
        when=when,
        topic=topic,
        project=explicit_project,
    )

    candidates = _candidates(
        store,
        request,
        active_session_id=active_session_id,
        project=inferred_project or None,
    )

    # A meaningful topic may identify another project. If the current project
    # has no match and no explicit project was requested, retry across projects.
    if not candidates and topic and not explicit_project and inferred_project:
        candidates = _candidates(
            store,
            request,
            active_session_id=active_session_id,
            project=None,
        )

    if not candidates:
        return _result(
            ok=False,
            error="no_matching_session",
            when=when,
            topic=topic,
            project=explicit_project or inferred_project,
        )

    # "latest" is explicitly deterministic. Relative windows can legitimately
    # contain several different jobs, so do not silently choose one for the user.
    if when != "latest" and len(candidates) > 1:
        visible = candidates[:8]
        return _result(
            ok=True,
            status="ambiguous",
            requires_user_choice=True,
            when=when,
            topic=topic,
            candidate_count=len(candidates),
            candidates=[
                _candidate_payload(candidate, index)
                for index, candidate in enumerate(visible, start=1)
            ],
        )

    return _queue_session(event_queue, candidates[0].session_id)

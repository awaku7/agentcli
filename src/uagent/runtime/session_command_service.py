"""Application services for session-oriented command operations.

The service layer returns provider- and host-neutral session search data. CLI
renderers remain responsible for translation and printing; persistence stays
behind the SessionStore interface supplied by the caller.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .memory_history_boundary import strip_derived_memory_context


@dataclass(frozen=True)
class LoadTargetResolution:
    """Resolved session target or a stable host-facing error code."""

    target: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class SessionSummarizePlan:
    """Bounded session rows selected for summarization."""

    target: str
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class SessionPrunePlan:
    """Session rows selected for a prune operation."""

    keep: int
    candidates: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class SessionWorkdirPlan:
    """Validated workdir transition data for a host to apply."""

    session_id: str
    target_path: str
    previous_path: str


@dataclass(frozen=True)
class SessionRestorePlan:
    """Host-agnostic plan for applying a loaded session to runtime state."""

    session_id: str
    messages: list[dict[str, Any]]
    tool_context: dict[str, Any]
    response_state: dict[str, Any] | None
    agent_state: dict[str, Any] | None = None


@dataclass(frozen=True)
class SessionContextState:
    """Persisted tool, agent, and Responses state needed when loading a session."""

    tool_context: dict[str, Any]
    response_state: dict[str, Any] | None
    agent_state: dict[str, Any] | None = None


@dataclass(frozen=True)
class SessionSearchResult:
    """One session-oriented search result ready for a host renderer."""

    row: dict[str, Any]
    matches: int
    hit_role: str
    hit_content: Any


class SessionCommandService:
    """Coordinate session persistence operations without producing UI output."""

    def __init__(self, store: Any) -> None:
        self._store = store

    @staticmethod
    def plan_summarize(
        rows: list[dict[str, Any]],
        *,
        target: str = "",
        limit: int = 10,
    ) -> SessionSummarizePlan:
        """Select a bounded set of sessions without reading or mutating them."""
        selected = rows
        if target:
            selected = [row for row in rows if row.get("session_id") == target]
        return SessionSummarizePlan(
            target=target,
            rows=tuple(selected[: max(0, limit)]),
        )

    @staticmethod
    def plan_prune(
        rows: list[dict[str, Any]],
        keep: int,
        *,
        active_session_id: str | None = None,
    ) -> SessionPrunePlan:
        """Select prune candidates without deleting or mutating persistence."""
        candidates = rows[keep:]
        if active_session_id:
            candidates = [
                row for row in candidates if row.get("session_id") != active_session_id
            ]
        return SessionPrunePlan(keep=keep, candidates=tuple(candidates))

    @staticmethod
    def plan_workdir(
        session_id: str,
        *,
        message_workdir: str | None = None,
        session_project_path: str | None = None,
        current_workdir: str | None = None,
    ) -> SessionWorkdirPlan | None:
        """Validate a recorded workdir without changing the process cwd."""
        candidate = message_workdir or session_project_path
        if not isinstance(candidate, str) or not candidate.strip():
            return None
        target_path = os.path.abspath(os.path.expanduser(candidate.strip()))
        if not os.path.isdir(target_path):
            return None
        previous_path = current_workdir or os.getcwd()
        return SessionWorkdirPlan(
            session_id=session_id,
            target_path=target_path,
            previous_path=previous_path,
        )

    @staticmethod
    def resolve_load_target(
        target: str,
        sessions: list[dict[str, Any]],
        *,
        search_results: dict[int, str] | None = None,
    ) -> LoadTargetResolution:
        """Resolve a session id or zero-based list/search index."""
        if not target:
            return LoadTargetResolution()
        if not target.isdigit():
            return LoadTargetResolution(target=target)
        index = int(target)
        if search_results and index in search_results:
            return LoadTargetResolution(target=str(search_results[index]))
        if 0 <= index < len(sessions):
            return LoadTargetResolution(target=str(sessions[index]["session_id"]))
        return LoadTargetResolution(error="index_out_of_range")

    def load_context_state(self, session_id: str) -> SessionContextState:
        """Read persisted tool and Responses state without mutating a host."""
        try:
            loaded_tool_context = self._store.latest_tool_context(session_id)
        except Exception:
            loaded_tool_context = {}
        tool_context = (
            dict(loaded_tool_context) if isinstance(loaded_tool_context, dict) else {}
        )
        try:
            response_state = self._store.latest_response_state(session_id)
        except Exception:
            response_state = None
        try:
            agent_state = self._store.get_agent_state(session_id)
        except Exception:
            agent_state = None
        return SessionContextState(
            tool_context=tool_context,
            response_state=(
                dict(response_state) if isinstance(response_state, dict) else None
            ),
            agent_state=(dict(agent_state) if isinstance(agent_state, dict) else None),
        )

    def build_restore_plan(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        *,
        system_prompt: str | None = None,
        state: SessionContextState | None = None,
    ) -> SessionRestorePlan:
        """Prepare loaded messages and persisted state without host mutation."""
        restored_messages = strip_derived_memory_context(messages)
        if system_prompt and not any(
            isinstance(message, dict) and message.get("role") == "system"
            for message in restored_messages
        ):
            restored_messages.insert(0, {"role": "system", "content": system_prompt})
        persisted = state or self.load_context_state(session_id)
        return SessionRestorePlan(
            session_id=session_id,
            messages=restored_messages,
            tool_context=dict(persisted.tool_context),
            response_state=(
                dict(persisted.response_state)
                if persisted.response_state is not None
                else None
            ),
            agent_state=(
                dict(persisted.agent_state)
                if persisted.agent_state is not None
                else None
            ),
        )

    def search(
        self,
        query: str,
        *,
        project: str | None = None,
        sort_keys: tuple[str, ...] = ("date", "matches"),
    ) -> list[SessionSearchResult]:
        """Search, collapse, enrich, and sort message hits by session.

        ``SessionStore.search`` returns message-level hits. The command UI
        displays one row per session, so this service owns that projection and
        leaves formatting and translation of the matching message to the caller.
        Derived system context is intentionally excluded from episodic search.
        """
        results = [
            row
            for row in self._store.search(query, project=project)
            if str(row.get("role") or "") != "system"
        ]
        if not results:
            return []

        session_rows: dict[str, dict[str, Any]] = {}
        session_match_counts: dict[str, int] = {}
        session_latest_dates: dict[str, str] = {}
        for row in results:
            session_id = row["session_id"]
            session_rows.setdefault(session_id, row)
            session_match_counts[session_id] = (
                session_match_counts.get(session_id, 0) + 1
            )
            created_at = row.get("created_at") or ""
            if created_at > session_latest_dates.get(session_id, ""):
                session_latest_dates[session_id] = created_at

        search_sessions = list(session_rows.values())
        search_sessions.sort(
            key=lambda row: tuple(
                (
                    session_latest_dates.get(row["session_id"], "")
                    if key == "date"
                    else session_match_counts[row["session_id"]]
                )
                for key in sort_keys
            ),
            reverse=True,
        )

        session_details: dict[str, dict[str, Any]] = {}
        try:
            for detail_row in self._store.list_sessions():
                try:
                    session_details[str(detail_row.get("session_id"))] = detail_row
                except Exception:
                    continue
        except Exception:
            session_details = {}

        output: list[SessionSearchResult] = []
        for row in search_sessions:
            session_id = row["session_id"]
            detail = dict(session_details.get(session_id, row))
            detail["created_at"] = session_latest_dates.get(session_id) or detail.get(
                "created_at"
            )
            output.append(
                SessionSearchResult(
                    row=detail,
                    matches=session_match_counts[session_id],
                    hit_role=str(row.get("role") or ""),
                    hit_content=row.get("content"),
                )
            )
        return output


__all__ = [
    "LoadTargetResolution",
    "SessionCommandService",
    "SessionPrunePlan",
    "SessionContextState",
    "SessionRestorePlan",
    "SessionSearchResult",
    "SessionSummarizePlan",
    "SessionWorkdirPlan",
]

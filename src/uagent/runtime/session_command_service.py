"""Application services for session-oriented command operations.

The service layer returns provider- and host-neutral session search data. CLI
renderers remain responsible for translation and printing; persistence stays
behind the SessionStore interface supplied by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SessionContextState:
    """Persisted tool and Responses state needed when loading a session."""

    tool_context: dict[str, Any]
    response_state: dict[str, Any] | None


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
        return SessionContextState(
            tool_context=tool_context,
            response_state=(
                dict(response_state) if isinstance(response_state, dict) else None
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

        ``SessionStore.search`` returns message-level hits.  The command UI
        displays one row per session, so this service owns that projection and
        leaves formatting and translation of the matching message to the caller.
        """
        results = self._store.search(query, project=project)
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
    "SessionCommandService",
    "SessionContextState",
    "SessionSearchResult",
]

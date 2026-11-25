"""Full-text term index, session search and session summaries. (``SessionStore`` mixin, split out of session_store.py)."""

from __future__ import annotations

from typing import Any
import threading
import time

from . import text_terms
from .session_store_common import (
    _db_locked,
    _sanitize_text,
    redact_sensitive,
)


class _SearchIndexMixin:
    """Full-text term index, session search and session summaries.

    Mixed into ``SessionStore``; relies on its connection, lock and
    ``_execute``/``_require_session`` helpers."""

    def _index_message_terms_unlocked(self, message_id: int, content: str) -> None:
        """Record extracted search terms for one message.

        Indexing must never break message appends: any failure is
        swallowed, and a message whose analyzer is not available yet
        is left without a row so the backfill can retry it later.
        """
        if not text_terms.terms_enabled():
            return
        try:
            terms = text_terms.index_terms(content)
        except Exception:
            return
        if terms is None:
            return
        try:
            self._execute(
                "INSERT OR REPLACE INTO message_terms(message_id, terms) "
                "VALUES (?, ?)",
                (message_id, " ".join(terms)),
            )
        except Exception:
            pass

    def backfill_message_terms(self, *, limit: int = 200) -> int:
        """Index terms for stored messages that have no terms row yet.

        Returns how many messages were processed. Messages whose
        analyzer is unavailable are skipped and left for a later pass.
        """
        if not text_terms.terms_enabled():
            return 0
        processed = 0
        after_id = 0
        while processed < limit:
            # The shared connection is serialized by _db_lock (see
            # _db_locked). Hold it only around the SQL itself so the
            # comparatively slow tokenization in between cannot stall
            # foreground appends and searches.
            with self._db_lock:
                rows = self._execute(
                    """
                    SELECT m.message_id, m.content FROM messages m
                    LEFT JOIN message_terms t ON t.message_id = m.message_id
                    WHERE t.message_id IS NULL AND m.message_id > ?
                    ORDER BY m.message_id LIMIT 200
                    """,
                    (after_id,),
                ).fetchall()
            if not rows:
                break
            for row in rows:
                after_id = int(row["message_id"])
                try:
                    terms = text_terms.index_terms(str(row["content"] or ""))
                except Exception:
                    continue
                if terms is None:
                    continue
                with self._db_lock:
                    self._execute(
                        "INSERT OR REPLACE INTO message_terms(message_id, terms) "
                        "VALUES (?, ?)",
                        (after_id, " ".join(terms)),
                    )
                processed += 1
                if processed >= limit:
                    break
        return processed

    def _kick_terms_backfill(self) -> None:
        """Start the background term backfill at most once in a while."""
        if not text_terms.terms_enabled():
            return
        with self._terms_lock:
            if self._terms_thread_active:
                return
            if time.monotonic() - self._terms_last_finished < 300:
                return
            self._terms_thread_active = True
        thread = threading.Thread(
            target=self._run_terms_backfill,
            daemon=True,
            name="uag-session-terms-backfill",
        )
        thread.start()

    def _run_terms_backfill(self) -> None:
        try:
            while self.backfill_message_terms() > 0:
                # Stay polite: a large backlog must not churn at full
                # speed in the background.
                time.sleep(0.05)
        except Exception:
            pass
        finally:
            with self._terms_lock:
                self._terms_thread_active = False
                self._terms_last_finished = time.monotonic()

    @staticmethod
    def _term_match_clause(query: str) -> tuple[str, list[Any]]:
        """SQL fragment + params matching messages by extracted terms.

        Terms are stored space-joined, so a padded LIKE matches whole
        terms only. Returns an empty fragment when the query yields no
        terms (unsupported script, analyzer unavailable, or disabled).
        """
        if not text_terms.terms_enabled():
            return "", []
        try:
            terms = text_terms.query_terms(query)
        except Exception:
            return "", []
        if not terms:
            return "", []
        conditions: list[str] = []
        parameters: list[Any] = []
        for term in terms:
            escaped = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            conditions.append("(' ' || terms || ' ') LIKE ? ESCAPE '!'")
            parameters.append(f"% {escaped} %")
        clause = (
            " OR m.message_id IN (SELECT message_id FROM message_terms WHERE "
            + " OR ".join(conditions)
            + ")"
        )
        return clause, parameters

    @_db_locked
    def search_sessions(
        self, query: str, *, project: str | None = None
    ) -> list[dict[str, Any]]:
        """Return aggregated non-system message hits, one row per session.

        The command service applies its result limit only after this SQL-level
        aggregation, so a busy session cannot consume the entire hit window.
        ``search`` remains a message-level API with its existing contract.
        """
        if not query.strip():
            return []
        self._kick_terms_backfill()
        escaped_query = query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        query_like = f"%{escaped_query}%"
        fts_query = '"' + query.replace('"', '""') + '"'
        term_clause, term_parameters = self._term_match_clause(query)
        parameters: list[Any] = [fts_query, query_like, query_like, *term_parameters]
        project_clause = ""
        if project is not None:
            project_clause = " AND s.project = ?"
            parameters.append(project)
        rows = self._execute(
            """
            WITH matched AS (
                SELECT m.session_id, s.project, s.entry_point, m.message_id,
                       m.role, m.content, m.created_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY m.session_id ORDER BY m.message_id
                       ) AS hit_rank,
                       COUNT(*) OVER (PARTITION BY m.session_id) AS match_count,
                       MAX(m.created_at) OVER (
                           PARTITION BY m.session_id
                       ) AS latest_match_at
                FROM messages m
                JOIN sessions s ON s.session_id = m.session_id
                WHERE m.role != 'system'
                  AND (
                      m.message_id IN (
                          SELECT message_id FROM message_search
                          WHERE message_search MATCH ?
                      )
                      OR m.content LIKE ? ESCAPE '!'
                      OR m.payload_json LIKE ? ESCAPE '!'
            """
            + term_clause
            + """
                  )
            """
            + project_clause
            + """
            )
            SELECT session_id, project, entry_point, message_id,
                   role, content, created_at, match_count, latest_match_at
            FROM matched
            WHERE hit_rank = 1
            ORDER BY message_id
            """,
            tuple(parameters),
        ).fetchall()
        return [dict(row) for row in rows]

    @_db_locked
    def save_session_summary(self, session_id: str, summary: str) -> None:
        self._require_session(session_id)
        summary = _sanitize_text(
            redact_sensitive(
                _sanitize_text(
                    summary if isinstance(summary, str) else str(summary or "")
                )
            )
        ).strip()
        if not summary:
            raise ValueError("summary is empty")
        self._execute(
            "INSERT INTO session_summaries(session_id, summary) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, created_at=CURRENT_TIMESTAMP",
            (session_id, summary),
        )

    @_db_locked
    def get_session_summary(self, session_id: str) -> str | None:
        self._require_session(session_id)
        row = self._execute(
            "SELECT summary FROM session_summaries WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return None if row is None else str(row["summary"])

    @_db_locked
    def summary_is_stale(self, session_id: str) -> bool:
        """Return True when the session gained messages after its summary.

        A session that already has a summary still needs re-summarization
        when the conversation continued after the summary was created (for
        example after ``:load`` + more turns, or mid-session summarize).
        """
        self._require_session(session_id)
        row = self._execute(
            "SELECT "
            "(SELECT MAX(created_at) FROM messages WHERE session_id = ?) AS last_message_at, "
            "(SELECT created_at FROM session_summaries WHERE session_id = ?) AS summary_at",
            (session_id, session_id),
        ).fetchone()
        if row is None:
            return False
        last_message_at = row["last_message_at"]
        summary_at = row["summary_at"]
        if not last_message_at or not summary_at:
            return False
        return str(last_message_at) > str(summary_at)

    @_db_locked
    def search(
        self, query: str, *, project: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        self._kick_terms_backfill()
        escaped_query = query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        query_like = f"%{escaped_query}%"
        # MATCH accepts a query language. Quote user input so punctuation
        # (for example ``new-1``) cannot become an FTS operator or column
        # reference and turn an ordinary search into an OperationalError.
        fts_query = '"' + query.replace('"', '""') + '"'
        term_clause, term_parameters = self._term_match_clause(query)
        parameters: list[Any] = [
            fts_query,
            query_like,
            query_like,
            *term_parameters,
            max(1, limit),
        ]
        project_clause = ""
        if project is not None:
            project_clause = " AND s.project = ?"
            parameters.insert(-1, project)
        rows = self._execute(
            """
            SELECT m.session_id, s.project, s.entry_point, m.message_id,
                   m.role, m.content, m.created_at
            FROM messages m
            JOIN sessions s ON s.session_id = m.session_id
            WHERE (
                m.message_id IN (
                    SELECT message_id FROM message_search WHERE message_search MATCH ?
                ) OR m.content LIKE ? ESCAPE '!' OR m.payload_json LIKE ? ESCAPE '!'
            """
            + term_clause
            + """
            )
            """
            + project_clause
            + " ORDER BY m.message_id LIMIT ?",
            tuple(parameters),
        ).fetchall()
        return [dict(row) for row in rows]

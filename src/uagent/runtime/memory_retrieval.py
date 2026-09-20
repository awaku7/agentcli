"""Read-only shadow retrieval for legacy personal and shared memories.

This module deliberately does not write memory stores or alter model input.  It
adapts existing records into provider-neutral ``ContextCandidate`` instances
and returns diagnostics that can be compared with the current retrieval path.
The references emitted here are temporary snapshot references, not durable
memory IDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from .active_context import ContextCandidate

MemoryScope = Literal["personal", "shared"]

_TOKEN_RE = re.compile(r"[\w][\w./:#@+-]*", re.UNICODE)


@dataclass(frozen=True)
class MemoryShadowDiagnostic:
    """A metadata-only explanation for one shadow retrieval decision."""

    index: int
    action: Literal["candidate", "exclude"]
    reason: str
    item_id: str
    scope_status: str
    relevance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            "reason": self.reason,
            "item_id": self.item_id,
            "scope_status": self.scope_status,
            "relevance": self.relevance,
        }


@dataclass(frozen=True)
class MemoryShadowResult:
    """Read-only shadow output; no field contains the memory note body."""

    candidates: list[ContextCandidate]
    diagnostics: list[MemoryShadowDiagnostic]
    total_records: int
    eligible_records: int
    excluded_records: int

    def to_dict(self) -> dict[str, Any]:
        """Return diagnostics without copying memory text into telemetry."""
        return {
            "candidate_ids": [candidate.item_id for candidate in self.candidates],
            "candidate_count": len(self.candidates),
            "total_records": self.total_records,
            "eligible_records": self.eligible_records,
            "excluded_records": self.excluded_records,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _field(record: dict[str, Any], *names: str) -> str:
    for name in names:
        value = _clean(record.get(name))
        if value:
            return value
    return ""


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(value)}


def _char_ngrams(value: str, size: int = 2) -> set[str]:
    compact = "".join(value.casefold().split())
    if not compact:
        return set()
    if len(compact) < size:
        return {compact}
    return {compact[pos : pos + size] for pos in range(len(compact) - size + 1)}


def _relevance(query: str, note: str) -> float:
    """Return deterministic lexical relevance without an importance fallback."""
    normalized_query = _clean(query).casefold()
    normalized_note = _clean(note).casefold()
    if not normalized_query:
        return 0.5
    if normalized_query in normalized_note:
        return 1.0

    query_tokens = _tokens(normalized_query)
    note_tokens = _tokens(normalized_note)
    token_score = (
        len(query_tokens & note_tokens) / len(query_tokens) if query_tokens else 0.0
    )

    query_ngrams = _char_ngrams(normalized_query)
    note_ngrams = _char_ngrams(normalized_note)
    ngram_score = (
        len(query_ngrams & note_ngrams) / len(query_ngrams)
        if query_ngrams
        else 0.0
    )
    return max(token_score, ngram_score)


def _snapshot_id(scope: MemoryScope, index: int, revision: str) -> str:
    revision_part = _clean(revision) or "unknown"
    # This is intentionally position/revision based.  It must not be treated
    # as a durable source ID because legacy SQLite replace can reindex records.
    return f"memory-shadow:{revision_part}:{scope}:{index}"


def shadow_retrieve_memories(
    records: Sequence[dict[str, Any]],
    *,
    query: str = "",
    scope: MemoryScope,
    owner: str = "",
    project: str = "",
    backend_revision: str = "",
    max_candidates: int = 20,
) -> MemoryShadowResult:
    """Retrieve eligible memory candidates without changing runtime input.

    ``scope`` is required so personal and shared records cannot be silently
    promoted into one another.  Missing owner/project metadata is retained as
    ``legacy_unknown`` for shadow visibility, but is never inferred or changed.
    """
    if scope not in ("personal", "shared"):
        raise ValueError("scope must be personal or shared")
    if max_candidates < 0:
        raise ValueError("max_candidates must be non-negative")

    requested_owner = _clean(owner).casefold()
    requested_project = _clean(project).casefold()
    diagnostics: list[MemoryShadowDiagnostic] = []
    scored: list[tuple[float, float, int, ContextCandidate, str]] = []
    seen_notes: set[str] = set()

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            diagnostics.append(
                MemoryShadowDiagnostic(
                    index=index,
                    action="exclude",
                    reason="invalid_record",
                    item_id=_snapshot_id(scope, index, backend_revision),
                    scope_status="unknown",
                )
            )
            continue

        item_id = _snapshot_id(scope, index, backend_revision)
        record_scope = _field(record, "scope")
        if record_scope and record_scope.casefold() != scope:
            diagnostics.append(
                MemoryShadowDiagnostic(
                    index=index,
                    action="exclude",
                    reason="scope_mismatch",
                    item_id=item_id,
                    scope_status="mismatch",
                )
            )
            continue

        record_owner = _field(record, "owner", "owner_id", "user", "user_id")
        record_project = _field(record, "project", "project_id")
        owner_known = bool(record_owner)
        project_known = bool(record_project)
        if requested_owner and owner_known and record_owner.casefold() != requested_owner:
            diagnostics.append(
                MemoryShadowDiagnostic(
                    index=index,
                    action="exclude",
                    reason="owner_mismatch",
                    item_id=item_id,
                    scope_status="scoped",
                )
            )
            continue
        if (
            requested_project
            and project_known
            and record_project.casefold() != requested_project
        ):
            diagnostics.append(
                MemoryShadowDiagnostic(
                    index=index,
                    action="exclude",
                    reason="project_mismatch",
                    item_id=item_id,
                    scope_status="scoped",
                )
            )
            continue

        note = _field(record, "note")
        if not note:
            diagnostics.append(
                MemoryShadowDiagnostic(
                    index=index,
                    action="exclude",
                    reason="empty_note",
                    item_id=item_id,
                    scope_status="legacy_unknown" if not owner_known or not project_known else "scoped",
                )
            )
            continue

        normalized_note = note.casefold()
        scope_status = (
            "legacy_unknown" if not owner_known or not project_known else "scoped"
        )
        relevance = _relevance(query, note)
        if relevance <= 0.0:
            diagnostics.append(
                MemoryShadowDiagnostic(
                    index=index,
                    action="exclude",
                    reason="no_query_match",
                    item_id=item_id,
                    scope_status=scope_status,
                    relevance=relevance,
                )
            )
            continue
        if normalized_note in seen_notes:
            diagnostics.append(
                MemoryShadowDiagnostic(
                    index=index,
                    action="exclude",
                    reason="duplicate_note",
                    item_id=item_id,
                    scope_status=scope_status,
                    relevance=relevance,
                )
            )
            continue
        seen_notes.add(normalized_note)

        candidate = ContextCandidate(
            item_id=item_id,
            source="memory",
            section="memory",
            content=note,
            importance=None,
            relevance=relevance,
            recency=None,
            original_chars=len(note),
            reference=f"memory-shadow://{scope}/{index}?revision={_clean(backend_revision) or 'unknown'}",
        )
        timestamp = record.get("ts", record.get("created_at", 0))
        try:
            timestamp_score = float(timestamp)
        except (TypeError, ValueError):
            timestamp_score = 0.0
        scored.append((relevance, timestamp_score, index, candidate, scope_status))
        diagnostics.append(
            MemoryShadowDiagnostic(
                index=index,
                action="candidate",
                reason="query_match",
                item_id=item_id,
                scope_status=scope_status,
                relevance=relevance,
            )
        )

    scored.sort(key=lambda item: (-item[0], -item[1], -item[2]))
    candidates = [item[3] for item in scored[:max_candidates]]
    eligible_records = len(scored)
    excluded_records = len(records) - eligible_records
    return MemoryShadowResult(
        candidates=candidates,
        diagnostics=diagnostics,
        total_records=len(records),
        eligible_records=eligible_records,
        excluded_records=excluded_records,
    )


__all__ = [
    "MemoryShadowDiagnostic",
    "MemoryShadowResult",
    "MemoryScope",
    "shadow_retrieve_memories",
]

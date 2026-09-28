"""Bounded local authorization/ownership index for Phase 4D trace queries.

This process-local index is deliberately independent from the telemetry backend.
Backend data can never create or repair ownership records. The Web trace-query
route is added by a later Phase 4D slice; this module only provides the bounded,
fail-closed local authority that the route will consume.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

MAX_LOCAL_SEGMENTS_PER_TRACE = 64
MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE = 2000
MAX_LOCAL_SCOPE_TEXT_CHARS = 256

MAX_INDEX_TRACES = 4096
MAX_INDEX_SEGMENTS = 16384
MAX_INDEX_OWNED_SPANS = 65536
MAX_INDEX_ACCOUNTED_BYTES = 64 * 1024 * 1024
INDEX_TTL_SECONDS = 24 * 60 * 60

_SEMANTIC_KINDS = frozenset(
    {
        "invoke_agent",
        "chat",
        "execute_tool",
        "provider_sdk",
        "internal",
        "unknown",
    }
)

# Conservative retained-storage accounting. Text is charged at four bytes per
# Unicode code point in addition to fixed Python/container bookkeeping. The
# index intentionally has no unaccounted secondary span map or eviction queue.
_TRACE_RECORD_BYTES = 4096
_SEGMENT_RECORD_BYTES = 2048
_OWNED_SPAN_BYTES = 512
_TEXT_CODEPOINT_BYTES = 4


@dataclass(frozen=True)
class TraceAdmissionHandle:
    trace_id: str
    generation: int
    segment_root_span_id: str


@dataclass(frozen=True)
class OwnedSpanSnapshot:
    span_id: str
    semantic_kind: str


@dataclass(frozen=True)
class LocalSegmentSnapshot:
    root_span_id: str
    principal_id: str
    room_id: str
    project_id: str
    service: str
    entry_point: str
    private_session: bool
    server_bound_project: bool
    owned_spans: tuple[OwnedSpanSnapshot, ...]


@dataclass(frozen=True)
class TraceOwnershipSnapshot:
    trace_id: str
    generation: int
    first_admitted_monotonic: float
    expires_at_monotonic: float
    segments: tuple[LocalSegmentSnapshot, ...]


@dataclass(frozen=True)
class TraceOwnershipIndexStats:
    traces: int
    segments: int
    owned_spans: int
    accounted_bytes: int


@dataclass
class _SegmentRecord:
    root_span_id: str
    principal_id: str
    room_id: str
    project_id: str
    service: str
    entry_point: str
    private_session: bool
    server_bound_project: bool
    owned_spans: dict[str, str]
    accounted_bytes: int


@dataclass
class _TraceRecord:
    trace_id: str
    generation: int
    first_admitted_monotonic: float
    expires_at_monotonic: float
    segments: dict[str, _SegmentRecord]
    queryable: bool
    accounted_bytes: int


class TraceOwnershipIndex:
    """Thread-safe bounded Phase 4D local ownership index."""

    def __init__(self, *, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._traces: dict[str, _TraceRecord] = {}
        self._next_generation = 1
        self._segments = 0
        self._owned_spans = 0
        self._accounted_bytes = 0

    def admit_segment(
        self,
        *,
        trace_id: object,
        root_span_id: object,
        principal_id: object,
        room_id: object,
        project_id: object,
        service: object,
        entry_point: object,
        private_session: object,
        server_bound_project: object,
    ) -> TraceAdmissionHandle | None:
        if not _valid_trace_id(trace_id) or not _valid_span_id(root_span_id):
            return None
        scope_values = (principal_id, room_id, project_id, service, entry_point)
        if not all(_valid_scope_text(value) for value in scope_values):
            return None
        if type(private_session) is not bool or type(server_bound_project) is not bool:
            return None

        trace = trace_id
        root_span = root_span_id
        segment_bytes = (
            _segment_accounted_bytes(
                principal_id,
                room_id,
                project_id,
                service,
                entry_point,
            )
            + _OWNED_SPAN_BYTES
        )

        with self._lock:
            now = self._safe_now()
            if now is None:
                return None
            self._remove_expired_locked(now)
            record = self._traces.get(trace)
            is_new_trace = record is None
            if record is not None:
                if not record.queryable:
                    return None
                if root_span in record.segments:
                    return None
                if len(record.segments) >= MAX_LOCAL_SEGMENTS_PER_TRACE:
                    self._mark_non_queryable_locked(record)
                    return None
                if (
                    self._trace_owned_span_count(record)
                    >= MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE
                ):
                    self._mark_non_queryable_locked(record)
                    return None
                if self._span_exists_locked(record, root_span):
                    self._mark_non_queryable_locked(record)
                    return None

            delta_traces = 1 if is_new_trace else 0
            delta_bytes = segment_bytes + (_TRACE_RECORD_BYTES if is_new_trace else 0)
            if not self._reserve_locked(
                trace_id=trace,
                delta_traces=delta_traces,
                delta_segments=1,
                delta_spans=1,
                delta_bytes=delta_bytes,
                updating_existing=not is_new_trace,
            ):
                return None

            now = self._safe_now()
            if now is None:
                return None
            self._remove_expired_locked(now)
            if is_new_trace:
                generation = self._next_generation
                self._next_generation += 1
                record = _TraceRecord(
                    trace_id=trace,
                    generation=generation,
                    first_admitted_monotonic=now,
                    expires_at_monotonic=now + INDEX_TTL_SECONDS,
                    segments={},
                    queryable=True,
                    accounted_bytes=_TRACE_RECORD_BYTES,
                )
                self._traces[trace] = record
                self._accounted_bytes += _TRACE_RECORD_BYTES
            else:
                record = self._traces.get(trace)
                if record is None or not record.queryable:
                    return None

            segment = _SegmentRecord(
                root_span_id=root_span,
                principal_id=principal_id,
                room_id=room_id,
                project_id=project_id,
                service=service,
                entry_point=entry_point,
                private_session=private_session,
                server_bound_project=server_bound_project,
                owned_spans={root_span: "invoke_agent"},
                accounted_bytes=segment_bytes,
            )
            record.segments[root_span] = segment
            record.accounted_bytes += segment_bytes
            self._segments += 1
            self._owned_spans += 1
            self._accounted_bytes += segment_bytes
            return TraceAdmissionHandle(trace, record.generation, root_span)

    def register_span(
        self,
        handle: object,
        *,
        span_id: object,
        semantic_kind: object,
    ) -> bool:
        with self._lock:
            now = self._safe_now()
            if now is None:
                return False
            self._remove_expired_locked(now)
            record, segment = self._resolve_handle_locked(handle)
            if record is None or segment is None or not record.queryable:
                return False

            if not _valid_span_id(span_id) or not _valid_semantic_kind(semantic_kind):
                self._mark_non_queryable_locked(record)
                return False

            existing = self._find_span_locked(record, span_id)
            if existing is not None:
                existing_segment, existing_kind = existing
                if existing_segment is segment and existing_kind == semantic_kind:
                    return True
                self._mark_non_queryable_locked(record)
                return False

            if (
                self._trace_owned_span_count(record)
                >= MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE
            ):
                self._mark_non_queryable_locked(record)
                return False

            if not self._reserve_locked(
                trace_id=record.trace_id,
                delta_traces=0,
                delta_segments=0,
                delta_spans=1,
                delta_bytes=_OWNED_SPAN_BYTES,
                updating_existing=True,
            ):
                return False

            now = self._safe_now()
            if now is None:
                return False
            self._remove_expired_locked(now)
            record, segment = self._resolve_handle_locked(handle)
            if record is None or segment is None or not record.queryable:
                return False

            segment.owned_spans[span_id] = semantic_kind
            segment.accounted_bytes += _OWNED_SPAN_BYTES
            record.accounted_bytes += _OWNED_SPAN_BYTES
            self._owned_spans += 1
            self._accounted_bytes += _OWNED_SPAN_BYTES
            return True

    def lookup_segments(
        self,
        trace_id: object,
        *,
        max_segments: object = MAX_LOCAL_SEGMENTS_PER_TRACE,
        deadline: object,
    ) -> TraceOwnershipSnapshot | None:
        if not _valid_trace_id(trace_id):
            return None
        if (
            type(max_segments) is not int
            or not 1 <= max_segments <= MAX_LOCAL_SEGMENTS_PER_TRACE
        ):
            return None
        if not _valid_deadline(deadline):
            return None

        with self._lock:
            now = self._safe_now_before(deadline)
            if now is None:
                return None
            self._remove_expired_locked(now)
            record = self._traces.get(trace_id)
            if record is None or not record.queryable:
                return None
            if len(record.segments) > max_segments:
                return None

            segments: list[LocalSegmentSnapshot] = []
            total_spans = 0
            for segment in record.segments.values():
                if (
                    self._safe_now_before(
                        deadline, expires_at=record.expires_at_monotonic
                    )
                    is None
                ):
                    return None
                owned_items: list[OwnedSpanSnapshot] = []
                for span_id, semantic_kind in segment.owned_spans.items():
                    if (
                        self._safe_now_before(
                            deadline, expires_at=record.expires_at_monotonic
                        )
                        is None
                    ):
                        return None
                    total_spans += 1
                    if total_spans > MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE:
                        return None
                    owned_items.append(OwnedSpanSnapshot(span_id, semantic_kind))
                segments.append(
                    LocalSegmentSnapshot(
                        root_span_id=segment.root_span_id,
                        principal_id=segment.principal_id,
                        room_id=segment.room_id,
                        project_id=segment.project_id,
                        service=segment.service,
                        entry_point=segment.entry_point,
                        private_session=segment.private_session,
                        server_bound_project=segment.server_bound_project,
                        owned_spans=tuple(owned_items),
                    )
                )

            if not segments:
                return None
            if (
                self._safe_now_before(deadline, expires_at=record.expires_at_monotonic)
                is None
            ):
                return None
            if self._traces.get(trace_id) is not record:
                return None
            return TraceOwnershipSnapshot(
                trace_id=record.trace_id,
                generation=record.generation,
                first_admitted_monotonic=record.first_admitted_monotonic,
                expires_at_monotonic=record.expires_at_monotonic,
                segments=tuple(segments),
            )

    def generation_is_live(
        self,
        *,
        trace_id: object,
        generation: object,
        deadline: object,
    ) -> bool:
        if not _valid_trace_id(trace_id):
            return False
        if type(generation) is not int or generation <= 0:
            return False
        if not _valid_deadline(deadline):
            return False
        with self._lock:
            now = self._safe_now_before(deadline)
            if now is None:
                return False
            self._remove_expired_locked(now)
            record = self._traces.get(trace_id)
            return bool(
                record is not None
                and record.queryable
                and record.generation == generation
                and now < record.expires_at_monotonic
            )

    def delete_trace(self, trace_id: object) -> bool:
        if not _valid_trace_id(trace_id):
            return False
        with self._lock:
            return self._remove_trace_locked(trace_id)

    def stats(self) -> TraceOwnershipIndexStats:
        with self._lock:
            return TraceOwnershipIndexStats(
                traces=len(self._traces),
                segments=self._segments,
                owned_spans=self._owned_spans,
                accounted_bytes=self._accounted_bytes,
            )

    def _safe_now(self) -> float | None:
        try:
            value = self._monotonic()
            if type(value) not in {int, float} or isinstance(value, bool):
                return None
            value = float(value)
        except (OverflowError, TypeError, ValueError):
            return None
        if value < 0 or value != value or value == float("inf"):
            return None
        return value

    def _safe_now_before(
        self, deadline: float, *, expires_at: float | None = None
    ) -> float | None:
        now = self._safe_now()
        if now is None or now >= deadline:
            return None
        if expires_at is not None and now >= expires_at:
            return None
        return now

    def _resolve_handle_locked(
        self, handle: object
    ) -> tuple[_TraceRecord | None, _SegmentRecord | None]:
        if type(handle) is not TraceAdmissionHandle:
            return None, None
        record = self._traces.get(handle.trace_id)
        if record is None or record.generation != handle.generation:
            return None, None
        return record, record.segments.get(handle.segment_root_span_id)

    def _reserve_locked(
        self,
        *,
        trace_id: str,
        delta_traces: int,
        delta_segments: int,
        delta_spans: int,
        delta_bytes: int,
        updating_existing: bool,
    ) -> bool:
        if (
            delta_traces > MAX_INDEX_TRACES
            or delta_segments > MAX_INDEX_SEGMENTS
            or delta_spans > MAX_INDEX_OWNED_SPANS
            or delta_bytes > MAX_INDEX_ACCOUNTED_BYTES
        ):
            return False

        while True:
            now = self._safe_now()
            if now is None:
                return False
            self._remove_expired_locked(now)
            if updating_existing and trace_id not in self._traces:
                return False
            if not self._would_exceed_locked(
                delta_traces=delta_traces,
                delta_segments=delta_segments,
                delta_spans=delta_spans,
                delta_bytes=delta_bytes,
            ):
                return True
            oldest = self._oldest_trace_id_locked()
            if oldest is None:
                return False
            self._remove_trace_locked(oldest)
            if updating_existing and oldest == trace_id:
                return False

    def _would_exceed_locked(
        self,
        *,
        delta_traces: int,
        delta_segments: int,
        delta_spans: int,
        delta_bytes: int,
    ) -> bool:
        return bool(
            len(self._traces) + delta_traces > MAX_INDEX_TRACES
            or self._segments + delta_segments > MAX_INDEX_SEGMENTS
            or self._owned_spans + delta_spans > MAX_INDEX_OWNED_SPANS
            or self._accounted_bytes + delta_bytes > MAX_INDEX_ACCOUNTED_BYTES
        )

    def _oldest_trace_id_locked(self) -> str | None:
        if not self._traces:
            return None
        return min(
            self._traces.values(),
            key=lambda record: (record.first_admitted_monotonic, record.trace_id),
        ).trace_id

    def _remove_expired_locked(self, now: float) -> None:
        expired = [
            trace_id
            for trace_id, record in self._traces.items()
            if now >= record.expires_at_monotonic
        ]
        for trace_id in expired:
            self._remove_trace_locked(trace_id)

    def _remove_trace_locked(self, trace_id: str) -> bool:
        record = self._traces.pop(trace_id, None)
        if record is None:
            return False
        self._segments -= len(record.segments)
        self._owned_spans -= self._trace_owned_span_count(record)
        self._accounted_bytes -= record.accounted_bytes
        return True

    def _mark_non_queryable_locked(self, record: _TraceRecord) -> None:
        record.queryable = False

    def _trace_owned_span_count(self, record: _TraceRecord) -> int:
        return sum(len(segment.owned_spans) for segment in record.segments.values())

    def _span_exists_locked(self, record: _TraceRecord, span_id: str) -> bool:
        return self._find_span_locked(record, span_id) is not None

    def _find_span_locked(
        self, record: _TraceRecord, span_id: str
    ) -> tuple[_SegmentRecord, str] | None:
        for segment in record.segments.values():
            semantic_kind = segment.owned_spans.get(span_id)
            if semantic_kind is not None:
                return segment, semantic_kind
        return None


def _valid_trace_id(value: object) -> bool:
    return bool(
        type(value) is str
        and len(value) == 32
        and value != "0" * 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_span_id(value: object) -> bool:
    return bool(
        type(value) is str
        and len(value) == 16
        and value != "0" * 16
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_semantic_kind(value: object) -> bool:
    return type(value) is str and value in _SEMANTIC_KINDS


def _valid_scope_text(value: object) -> bool:
    return type(value) is str and len(value) <= MAX_LOCAL_SCOPE_TEXT_CHARS


def _valid_deadline(value: object) -> bool:
    try:
        if type(value) not in {int, float} or isinstance(value, bool):
            return False
        deadline = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    return deadline >= 0 and deadline == deadline and deadline != float("inf")


def _segment_accounted_bytes(*values: str) -> int:
    return _SEGMENT_RECORD_BYTES + _TEXT_CODEPOINT_BYTES * sum(
        len(value) for value in values
    )


__all__ = [
    "INDEX_TTL_SECONDS",
    "MAX_INDEX_ACCOUNTED_BYTES",
    "MAX_INDEX_OWNED_SPANS",
    "MAX_INDEX_SEGMENTS",
    "MAX_INDEX_TRACES",
    "MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE",
    "MAX_LOCAL_SCOPE_TEXT_CHARS",
    "MAX_LOCAL_SEGMENTS_PER_TRACE",
    "LocalSegmentSnapshot",
    "OwnedSpanSnapshot",
    "TraceAdmissionHandle",
    "TraceOwnershipIndex",
    "TraceOwnershipIndexStats",
    "TraceOwnershipSnapshot",
]

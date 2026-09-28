"""Bounded Phase 4D backend retrieval and ordinary-user trace projection."""

from __future__ import annotations

import threading
import time
import weakref
from dataclasses import dataclass
from typing import Protocol

MAX_BACKEND_DECODED_BYTES = 8 * 1024 * 1024
MAX_BACKEND_SPANS = 2000
MAX_BACKEND_PAGE_SPANS = 500
MAX_BACKEND_PAGES = 4
MAX_RETURNED_SPANS = 500
MAX_BACKEND_CURSOR_CHARS = 256

_HEX = frozenset("0123456789abcdef")
_SEMANTIC_NAMES = {
    "invoke_agent": "AGENT",
    "chat": "LLM",
    "execute_tool": "TOOL",
    "provider_sdk": "PROVIDER_SDK",
    "internal": "INTERNAL",
    "unknown": "UNKNOWN",
}
_TIME_FACTORS_NS = {"ms": 1_000_000, "us": 1_000, "ns": 1}
_TIME_MAX = {
    "ms": 9_007_199_254_740_991,
    "us": 9_007_199_254_740_991_999,
    "ns": 9_007_199_254_740_991_999_999,
}


@dataclass(frozen=True)
class TraceBackendSpanRecord:
    """Reviewed adapter output for one backend span record.

    Fields intentionally accept ``object`` so projection can apply exact runtime
    type gates without adapters coercing malformed backend values.
    """

    trace_id: object
    span_id: object
    parent_span_id: object
    start_time: object
    start_unit: object
    end_time: object
    end_unit: object
    status: object = None


@dataclass(frozen=True)
class TraceBackendPage:
    """One already-bounded decoded page returned by a trusted backend adapter."""

    records: tuple[TraceBackendSpanRecord, ...]
    decoded_bytes: int
    next_cursor: str | None = None
    partial: bool = False


class TraceQueryBackendAdapter(Protocol):
    """Trusted backend adapter contract used only after UAG authorization."""

    def fetch_trace_page(
        self,
        *,
        trace_id: str,
        cursor: str | None,
        max_spans: int,
        max_decoded_bytes: int,
        deadline: float,
    ) -> TraceBackendPage: ...


@dataclass(frozen=True)
class TraceViewProjection:
    """Closed ordinary-user trace projection."""

    trace_id: str
    partial: bool
    spans: tuple[dict[str, object], ...]

    def as_json(self) -> dict[str, object]:
        return {
            "schema_version": "uag.trace_view.v1",
            "trace_id": self.trace_id,
            "partial": self.partial,
            "spans": [dict(span) for span in self.spans],
        }


@dataclass(frozen=True)
class _CandidateSpan:
    span_id: str
    parent_span_id: str | None
    parent_malformed: bool
    name: str
    start_time: int
    end_time: int
    duration_ms: int
    status_code: str


_ADAPTER_LOCK = threading.Lock()
_BOUND_BACKEND_REF: weakref.ReferenceType[object] | None = None
_BOUND_ADAPTER: object | None = None


def install_trace_query_backend_adapter(*, backend: object, adapter: object) -> None:
    """Bind one trusted query adapter to one exact active backend object.

    This is an application-integration hook, not a request/configuration surface.
    Replacing the observability backend automatically makes the old binding
    unusable because lookup is by object identity.
    """

    fetch_page = getattr(adapter, "fetch_trace_page", None)
    if backend is None or adapter is None or not callable(fetch_page):
        raise TypeError("invalid trace query backend adapter")
    try:
        backend_ref = weakref.ref(backend)
    except TypeError as exc:
        raise TypeError("trace query backend must support weak references") from exc
    global _BOUND_BACKEND_REF, _BOUND_ADAPTER
    with _ADAPTER_LOCK:
        _BOUND_BACKEND_REF = backend_ref
        _BOUND_ADAPTER = adapter


def clear_trace_query_backend_adapter(*, backend: object | None = None) -> None:
    """Clear the trusted adapter binding, optionally only for one backend."""

    global _BOUND_BACKEND_REF, _BOUND_ADAPTER
    with _ADAPTER_LOCK:
        bound_backend = _BOUND_BACKEND_REF() if _BOUND_BACKEND_REF is not None else None
        if backend is not None and bound_backend is not backend:
            return
        _BOUND_BACKEND_REF = None
        _BOUND_ADAPTER = None


def get_trace_query_backend_adapter(backend: object) -> object | None:
    """Return the adapter bound to this exact backend instance, if any."""

    global _BOUND_BACKEND_REF, _BOUND_ADAPTER
    if backend is None:
        return None
    with _ADAPTER_LOCK:
        if _BOUND_BACKEND_REF is None:
            return None
        bound_backend = _BOUND_BACKEND_REF()
        if bound_backend is None:
            _BOUND_BACKEND_REF = None
            _BOUND_ADAPTER = None
            return None
        if bound_backend is backend:
            return _BOUND_ADAPTER
        return None


def _deadline_alive(deadline: float) -> bool:
    try:
        now = time.monotonic()
    except Exception:
        return False
    return type(now) in {int, float} and not isinstance(now, bool) and now < deadline


def _canonical_trace_id(value: object) -> str | None:
    if (
        type(value) is str
        and len(value) == 32
        and value != "0" * 32
        and all(character in _HEX for character in value)
    ):
        return value
    return None


def _canonical_span_id(value: object) -> str | None:
    if (
        type(value) is str
        and len(value) == 16
        and value != "0" * 16
        and all(character in _HEX for character in value)
    ):
        return value
    return None


def _ascii_lower(value: str) -> str:
    chars: list[str] = []
    for character in value:
        code = ord(character)
        if 65 <= code <= 90:
            chars.append(chr(code + 32))
        else:
            chars.append(character)
    return "".join(chars)


def _normalize_status(value: object) -> str:
    if value is None:
        return "UNSET"
    if type(value) is not str or len(value) > 16:
        return "UNSET"
    normalized = _ascii_lower(value.strip(" \t"))
    if normalized in {"ok", "success", "completed"}:
        return "OK"
    if normalized in {"error", "failed", "failure"}:
        return "ERROR"
    return "UNSET"


def _canonical_time(value: object, unit: object) -> tuple[int, int] | None:
    if type(unit) is not str or unit not in _TIME_FACTORS_NS:
        return None
    if type(value) is not int or isinstance(value, bool):
        return None
    maximum = _TIME_MAX[unit]
    if value < 0 or value > maximum:
        return None
    return value, _TIME_FACTORS_NS[unit]


def _canonical_timing(record: TraceBackendSpanRecord) -> tuple[int, int, int] | None:
    start = _canonical_time(record.start_time, record.start_unit)
    end = _canonical_time(record.end_time, record.end_unit)
    if start is None or end is None:
        return None
    start_raw, start_factor = start
    end_raw, end_factor = end
    if end_raw * end_factor < start_raw * start_factor:
        return None
    start_ms = start_raw * start_factor // 1_000_000
    end_ms = end_raw * end_factor // 1_000_000
    if end_ms < start_ms:
        return None
    return start_ms, end_ms, end_ms - start_ms


def _valid_cursor(value: object) -> bool:
    if type(value) is not str or not 1 <= len(value) <= MAX_BACKEND_CURSOR_CHARS:
        return False
    return not any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _fetch_records(
    adapter: object,
    *,
    trace_id: str,
    deadline: float,
) -> tuple[tuple[TraceBackendSpanRecord, ...], bool] | None:
    fetch_page = getattr(adapter, "fetch_trace_page", None)
    if not callable(fetch_page):
        return None

    records: list[TraceBackendSpanRecord] = []
    decoded_bytes = 0
    cursor: str | None = None
    seen_cursors: set[str] = set()
    partial = False

    for page_number in range(MAX_BACKEND_PAGES):
        if not _deadline_alive(deadline):
            return None
        remaining_spans = MAX_BACKEND_SPANS - len(records)
        remaining_bytes = MAX_BACKEND_DECODED_BYTES - decoded_bytes
        if remaining_spans <= 0 or remaining_bytes <= 0:
            partial = True
            break
        page_span_limit = min(MAX_BACKEND_PAGE_SPANS, remaining_spans)
        try:
            page = fetch_page(
                trace_id=trace_id,
                cursor=cursor,
                max_spans=page_span_limit,
                max_decoded_bytes=remaining_bytes,
                deadline=deadline,
            )
        except Exception:
            return None
        if not _deadline_alive(deadline):
            return None
        if type(page) is not TraceBackendPage:
            return None
        if type(page.records) is not tuple or len(page.records) > page_span_limit:
            return None
        if type(page.decoded_bytes) is not int or isinstance(page.decoded_bytes, bool):
            return None
        if page.decoded_bytes < 0 or page.decoded_bytes > remaining_bytes:
            return None
        if type(page.partial) is not bool:
            return None
        for record in page.records:
            if type(record) is not TraceBackendSpanRecord:
                return None
        records.extend(page.records)
        decoded_bytes += page.decoded_bytes
        partial = partial or page.partial

        next_cursor = page.next_cursor
        if next_cursor is None:
            return tuple(records), partial
        if not _valid_cursor(next_cursor):
            return None
        if next_cursor in seen_cursors:
            partial = True
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor

        if len(records) >= MAX_BACKEND_SPANS:
            partial = True
            break
        if decoded_bytes >= MAX_BACKEND_DECODED_BYTES:
            partial = True
            break
        if page_number + 1 >= MAX_BACKEND_PAGES:
            partial = True
            break

    return tuple(records), partial


def project_trace_view(
    adapter: object,
    *,
    trace_id: str,
    authorized_span_kinds: tuple[tuple[str, str], ...],
    initial_partial: bool,
    deadline: float,
) -> TraceViewProjection | None:
    """Fetch bounded backend pages and build the closed v1 projection."""

    if _canonical_trace_id(trace_id) != trace_id:
        return None
    if type(authorized_span_kinds) is not tuple or not authorized_span_kinds:
        return None
    if type(initial_partial) is not bool:
        return None

    authorized: dict[str, str] = {}
    for item in authorized_span_kinds:
        if type(item) is not tuple or len(item) != 2:
            return None
        span_id, semantic_kind = item
        if _canonical_span_id(span_id) != span_id:
            return None
        if type(semantic_kind) is not str or semantic_kind not in _SEMANTIC_NAMES:
            return None
        if span_id in authorized:
            return None
        authorized[span_id] = semantic_kind
        if len(authorized) > MAX_BACKEND_SPANS:
            return None

    fetched = _fetch_records(adapter, trace_id=trace_id, deadline=deadline)
    if fetched is None:
        return None
    records, partial = fetched
    partial = partial or initial_partial

    matching: list[tuple[str, TraceBackendSpanRecord]] = []
    counts: dict[str, int] = {}
    for record in records:
        if not _deadline_alive(deadline):
            return None
        record_trace_id = _canonical_trace_id(record.trace_id)
        if record_trace_id != trace_id:
            partial = True
            continue
        span_id = _canonical_span_id(record.span_id)
        if span_id is None:
            partial = True
            continue
        counts[span_id] = counts.get(span_id, 0) + 1
        matching.append((span_id, record))

    duplicate_ids = {span_id for span_id, count in counts.items() if count > 1}
    if duplicate_ids:
        partial = True

    candidates: list[_CandidateSpan] = []
    candidate_ids: set[str] = set()
    for span_id, record in matching:
        if not _deadline_alive(deadline):
            return None
        if span_id in duplicate_ids:
            continue
        semantic_kind = authorized.get(span_id)
        if semantic_kind is None:
            partial = True
            continue
        timing = _canonical_timing(record)
        if timing is None:
            partial = True
            continue
        start_ms, end_ms, duration_ms = timing

        parent_malformed = False
        parent_span_id: str | None = None
        if record.parent_span_id is not None:
            parent_span_id = _canonical_span_id(record.parent_span_id)
            if parent_span_id is None:
                parent_malformed = True
                partial = True

        candidate = _CandidateSpan(
            span_id=span_id,
            parent_span_id=parent_span_id,
            parent_malformed=parent_malformed,
            name=_SEMANTIC_NAMES[semantic_kind],
            start_time=start_ms,
            end_time=end_ms,
            duration_ms=duration_ms,
            status_code=_normalize_status(record.status),
        )
        candidates.append(candidate)
        candidate_ids.add(span_id)

    if set(authorized) - candidate_ids:
        partial = True

    candidates.sort(key=lambda item: (item.start_time, item.span_id))
    if len(candidates) > MAX_RETURNED_SPANS:
        candidates = candidates[:MAX_RETURNED_SPANS]
        partial = True

    returned_ids = {item.span_id for item in candidates}
    spans: list[dict[str, object]] = []
    for candidate in candidates:
        if not _deadline_alive(deadline):
            return None
        payload: dict[str, object] = {
            "span_id": candidate.span_id,
            "parent_omitted": False,
            "name": candidate.name,
            "start_time": candidate.start_time,
            "end_time": candidate.end_time,
            "duration_ms": candidate.duration_ms,
            "status_code": candidate.status_code,
        }
        if candidate.parent_span_id is not None:
            if candidate.parent_span_id in returned_ids:
                payload["parent_span_id"] = candidate.parent_span_id
            else:
                payload["parent_omitted"] = True
                partial = True
        elif candidate.parent_malformed:
            payload["parent_omitted"] = True
        spans.append(payload)

    return TraceViewProjection(trace_id=trace_id, partial=partial, spans=tuple(spans))


__all__ = [
    "MAX_BACKEND_DECODED_BYTES",
    "MAX_BACKEND_PAGE_SPANS",
    "MAX_BACKEND_PAGES",
    "MAX_BACKEND_SPANS",
    "MAX_RETURNED_SPANS",
    "TraceBackendPage",
    "TraceBackendSpanRecord",
    "TraceQueryBackendAdapter",
    "TraceViewProjection",
    "clear_trace_query_backend_adapter",
    "get_trace_query_backend_adapter",
    "install_trace_query_backend_adapter",
    "project_trace_view",
]

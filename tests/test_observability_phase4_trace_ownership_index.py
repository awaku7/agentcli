from __future__ import annotations

from uagent.runtime.observability.trace_ownership_index import (
    INDEX_TTL_SECONDS,
    MAX_INDEX_ACCOUNTED_BYTES,
    MAX_INDEX_TRACES,
    MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE,
    MAX_LOCAL_SEGMENTS_PER_TRACE,
    TraceAdmissionHandle,
    TraceOwnershipIndex,
)


class _Clock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value
        self.step = 0.0

    def __call__(self) -> float:
        current = self.value
        self.value += self.step
        return current


def _trace(value: int) -> str:
    return f"{value:032x}"


def _span(value: int) -> str:
    return f"{value:016x}"


def _admit(
    index: TraceOwnershipIndex,
    *,
    trace: int = 1,
    root: int = 1,
    text: str = "scope",
) -> TraceAdmissionHandle | None:
    return index.admit_segment(
        trace_id=_trace(trace),
        root_span_id=_span(root),
        principal_id=f"principal-{text}",
        room_id=f"room-{text}",
        project_id=f"project-{text}",
        service=f"service-{text}",
        entry_point=f"entry-{text}",
        private_session=False,
        server_bound_project=False,
    )


def test_phase4d_index_admits_root_and_keeps_semantic_kind_immutable() -> None:
    clock = _Clock()
    index = TraceOwnershipIndex(monotonic=clock)
    handle = _admit(index)
    assert handle is not None

    assert index.register_span(handle, span_id=_span(2), semantic_kind="chat") is True
    assert index.register_span(handle, span_id=_span(2), semantic_kind="chat") is True

    snapshot = index.lookup_segments(_trace(1), deadline=10.0)
    assert snapshot is not None
    assert snapshot.generation == handle.generation
    assert len(snapshot.segments) == 1
    assert [
        (item.span_id, item.semantic_kind) for item in snapshot.segments[0].owned_spans
    ] == [
        (_span(1), "invoke_agent"),
        (_span(2), "chat"),
    ]
    assert index.stats().owned_spans == 2


def test_phase4d_index_rejects_noncanonical_ids_and_unbounded_scope_text() -> None:
    index = TraceOwnershipIndex(monotonic=_Clock())
    kwargs = dict(
        root_span_id=_span(1),
        principal_id="principal",
        room_id="room",
        project_id="project",
        service="service",
        entry_point="web",
        private_session=False,
        server_bound_project=False,
    )

    assert index.admit_segment(trace_id="0" * 32, **kwargs) is None
    assert index.admit_segment(trace_id="A" * 32, **kwargs) is None
    assert (
        index.admit_segment(
            trace_id=_trace(1),
            **{**kwargs, "principal_id": "p" * 257},
        )
        is None
    )
    assert (
        index.admit_segment(
            trace_id=_trace(1),
            **{**kwargs, "private_session": 1},
        )
        is None
    )

    class _Text(str):
        pass

    assert (
        index.admit_segment(
            trace_id=_trace(1),
            **{**kwargs, "service": _Text("service")},
        )
        is None
    )


def test_phase4d_conflicting_semantic_kind_makes_trace_non_queryable() -> None:
    index = TraceOwnershipIndex(monotonic=_Clock())
    handle = _admit(index)
    assert handle is not None
    assert index.register_span(handle, span_id=_span(2), semantic_kind="chat") is True

    assert (
        index.register_span(handle, span_id=_span(2), semantic_kind="provider_sdk")
        is False
    )
    assert index.lookup_segments(_trace(1), deadline=10.0) is None


def test_phase4d_explicit_unknown_kind_is_valid() -> None:
    index = TraceOwnershipIndex(monotonic=_Clock())
    handle = _admit(index)
    assert handle is not None
    assert (
        index.register_span(handle, span_id=_span(2), semantic_kind="unknown") is True
    )

    snapshot = index.lookup_segments(_trace(1), deadline=10.0)
    assert snapshot is not None
    assert snapshot.segments[0].owned_spans[-1].semantic_kind == "unknown"


def test_phase4d_unsupported_kind_marks_generation_non_queryable() -> None:
    index = TraceOwnershipIndex(monotonic=_Clock())
    handle = _admit(index)
    assert handle is not None

    assert index.register_span(handle, span_id=_span(2), semantic_kind="model") is False
    assert index.lookup_segments(_trace(1), deadline=10.0) is None


def test_phase4d_segment_65_marks_trace_non_queryable() -> None:
    index = TraceOwnershipIndex(monotonic=_Clock())
    for root in range(1, MAX_LOCAL_SEGMENTS_PER_TRACE + 1):
        assert _admit(index, root=root, text=str(root)) is not None

    assert index.stats().segments == MAX_LOCAL_SEGMENTS_PER_TRACE
    assert _admit(index, root=MAX_LOCAL_SEGMENTS_PER_TRACE + 1) is None
    assert index.lookup_segments(_trace(1), deadline=10.0) is None


def test_phase4d_owned_span_2001_marks_trace_non_queryable() -> None:
    index = TraceOwnershipIndex(monotonic=_Clock())
    handle = _admit(index)
    assert handle is not None

    for value in range(2, MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE + 1):
        assert index.register_span(
            handle, span_id=_span(value), semantic_kind="internal"
        )

    assert index.stats().owned_spans == MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE
    assert (
        index.register_span(
            handle,
            span_id=_span(MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE + 1),
            semantic_kind="internal",
        )
        is False
    )
    assert index.lookup_segments(_trace(1), deadline=10.0) is None


def test_phase4d_ttl_is_from_first_admission_and_stale_handle_cannot_revive() -> None:
    clock = _Clock()
    index = TraceOwnershipIndex(monotonic=clock)
    first = _admit(index, root=1)
    assert first is not None

    clock.value = INDEX_TTL_SECONDS - 1
    second = _admit(index, root=2)
    assert second is not None
    assert second.generation == first.generation

    clock.value = INDEX_TTL_SECONDS
    assert index.lookup_segments(_trace(1), deadline=INDEX_TTL_SECONDS + 10) is None
    assert index.register_span(first, span_id=_span(3), semantic_kind="chat") is False

    replacement = _admit(index, root=3)
    assert replacement is not None
    assert replacement.generation != first.generation


def test_phase4d_delete_invalidates_generation_before_response_recheck() -> None:
    clock = _Clock()
    index = TraceOwnershipIndex(monotonic=clock)
    handle = _admit(index)
    assert handle is not None
    snapshot = index.lookup_segments(_trace(1), deadline=10.0)
    assert snapshot is not None
    assert index.generation_is_live(
        trace_id=snapshot.trace_id,
        generation=snapshot.generation,
        deadline=10.0,
    )

    assert index.delete_trace(_trace(1)) is True
    assert not index.generation_is_live(
        trace_id=snapshot.trace_id,
        generation=snapshot.generation,
        deadline=10.0,
    )
    assert index.register_span(handle, span_id=_span(2), semantic_kind="chat") is False


def test_phase4d_aggregate_trace_capacity_evicts_oldest_whole_trace() -> None:
    clock = _Clock()
    index = TraceOwnershipIndex(monotonic=clock)

    for value in range(1, MAX_INDEX_TRACES + 2):
        assert _admit(index, trace=value) is not None

    stats = index.stats()
    assert stats.traces == MAX_INDEX_TRACES
    assert index.lookup_segments(_trace(1), deadline=10.0) is None
    assert index.lookup_segments(_trace(2), deadline=10.0) is not None
    assert (
        index.lookup_segments(_trace(MAX_INDEX_TRACES + 1), deadline=10.0) is not None
    )


def test_phase4d_accounted_byte_ceiling_evicts_whole_traces() -> None:
    clock = _Clock()
    index = TraceOwnershipIndex(monotonic=clock)
    text = "x" * 246

    # Five stored scope strings are each <= 256 chars once their prefixes are
    # added. Filling 137 traces with 64 segments each exceeds the 64 MiB
    # conservative accounting budget before the aggregate segment ceiling.
    for trace_value in range(1, 138):
        for root in range(1, MAX_LOCAL_SEGMENTS_PER_TRACE + 1):
            assert (
                _admit(
                    index,
                    trace=trace_value,
                    root=root,
                    text=text,
                )
                is not None
            )

    stats = index.stats()
    assert stats.accounted_bytes <= MAX_INDEX_ACCOUNTED_BYTES
    assert stats.traces < 137
    assert index.lookup_segments(_trace(1), deadline=10.0) is None
    assert index.lookup_segments(_trace(137), deadline=10.0) is not None


def test_phase4d_lookup_honors_one_shared_deadline_during_snapshot() -> None:
    clock = _Clock()
    index = TraceOwnershipIndex(monotonic=clock)
    assert _admit(index, root=1) is not None
    assert _admit(index, root=2) is not None

    clock.value = 0.0
    clock.step = 1.0
    assert index.lookup_segments(_trace(1), deadline=2.5) is None


def test_phase4d_lookup_max_segments_is_bounded_without_poisoning_trace() -> None:
    index = TraceOwnershipIndex(monotonic=_Clock())
    assert _admit(index, root=1) is not None
    assert _admit(index, root=2) is not None

    assert index.lookup_segments(_trace(1), max_segments=1, deadline=10.0) is None
    assert index.lookup_segments(_trace(1), max_segments=2, deadline=10.0) is not None

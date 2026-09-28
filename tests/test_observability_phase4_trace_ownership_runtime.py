from __future__ import annotations

import threading
import time

import pytest

from uagent.runtime.execution import (
    apply_turn_context_to_current_agent_span,
    lifecycle_execution,
)
from uagent.runtime.identity_context import TurnContext
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.observability.trace_ownership_runtime import (
    _reset_trace_ownership_runtime_for_tests,
    _runtime_index_snapshot_for_tests,
    _runtime_state,
    admit_current_segment,
    install_trace_ownership_span_binding,
)


def _turn(*, room_id: str = "room-1") -> TurnContext:
    return TurnContext(
        principal_id="principal-1",
        room_id=room_id,
        project_id="project-1",
        session_id="session-1",
        entry_point="cli",
        authenticated=True,
        authn_kind="local",
    )


def _settings(*, enabled: bool = True) -> ObservabilitySettings:
    return ObservabilitySettings(
        enabled=True,
        trace_query_enabled=enabled,
    )


def _backend(monkeypatch, settings: ObservabilitySettings):
    pytest.importorskip("opentelemetry.sdk")
    from uagent.runtime.observability.otel_backend import create_otel_backend

    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "none")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "uagent-test")
    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        lambda: settings,
    )
    backend = create_otel_backend(settings)
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: backend,
    )
    install_trace_ownership_span_binding()
    return backend


def _snapshot(trace_id: str):
    index, _epoch = _runtime_index_snapshot_for_tests()
    return index.lookup_segments(trace_id, deadline=time.monotonic() + 5.0)


def setup_function() -> None:
    _reset_trace_ownership_runtime_for_tests()


def test_phase4d_admission_requires_exact_local_span(monkeypatch) -> None:
    from uagent.runtime.observability.noop import NOOP_SPAN

    backend = _backend(monkeypatch, _settings())
    try:
        with backend.start_span("invoke_agent"):
            current = backend.current_trace_ids()
            assert current.trace_id is not None
            assert current.span_id is not None
            assert admit_current_segment(backend, _turn(), NOOP_SPAN) is None

        index, _epoch = _runtime_index_snapshot_for_tests()
        assert index.stats().traces == 0
    finally:
        backend.shutdown()


def test_phase4d_runtime_binds_root_and_closed_child_semantic_kinds(
    monkeypatch,
) -> None:
    backend = _backend(monkeypatch, _settings())
    try:
        with lifecycle_execution(turn_context=_turn()):
            root = backend.current_trace_ids()
            assert root.trace_id is not None
            assert root.span_id is not None

            with backend.start_span("chat"):
                chat = backend.current_trace_ids()
                with backend.start_span("provider_sdk"):
                    provider = backend.current_trace_ids()

            with backend.start_span("execute_tool"):
                tool = backend.current_trace_ids()
            with backend.start_span("retrieval"):
                internal = backend.current_trace_ids()
            with backend.start_span("invoke_agent"):
                nested_agent = backend.current_trace_ids()

        snapshot = _snapshot(root.trace_id)
        assert snapshot is not None
        assert len(snapshot.segments) == 1
        segment = snapshot.segments[0]
        assert segment.root_span_id == root.span_id
        assert segment.principal_id == "principal-1"
        assert segment.room_id == "room-1"
        assert segment.project_id == "project-1"
        assert segment.service == "uagent-test"
        assert segment.entry_point == "cli"
        assert {(item.span_id, item.semantic_kind) for item in segment.owned_spans} == {
            (root.span_id, "invoke_agent"),
            (chat.span_id, "chat"),
            (provider.span_id, "provider_sdk"),
            (tool.span_id, "execute_tool"),
            (internal.span_id, "internal"),
            (nested_agent.span_id, "invoke_agent"),
        }
    finally:
        backend.shutdown()


def test_phase4d_nested_lifecycle_creates_second_segment_and_restores_parent(
    monkeypatch,
) -> None:
    backend = _backend(monkeypatch, _settings())
    try:
        with lifecycle_execution(turn_context=_turn(room_id="outer")):
            outer = backend.current_trace_ids()
            assert outer.trace_id is not None
            assert outer.span_id is not None

            with lifecycle_execution(turn_context=_turn(room_id="inner")):
                inner = backend.current_trace_ids()
                assert inner.trace_id == outer.trace_id
                assert inner.span_id != outer.span_id
                with backend.start_span("chat"):
                    inner_chat = backend.current_trace_ids()

            with backend.start_span("execute_tool"):
                outer_tool = backend.current_trace_ids()

        snapshot = _snapshot(outer.trace_id)
        assert snapshot is not None
        assert len(snapshot.segments) == 2
        by_root = {segment.root_span_id: segment for segment in snapshot.segments}
        assert by_root[outer.span_id].room_id == "outer"
        assert by_root[inner.span_id].room_id == "inner"
        assert {
            (item.span_id, item.semantic_kind)
            for item in by_root[outer.span_id].owned_spans
        } == {
            (outer.span_id, "invoke_agent"),
            (outer_tool.span_id, "execute_tool"),
        }
        assert {
            (item.span_id, item.semantic_kind)
            for item in by_root[inner.span_id].owned_spans
        } == {
            (inner.span_id, "invoke_agent"),
            (inner_chat.span_id, "chat"),
        }
    finally:
        backend.shutdown()


def test_phase4d_feature_off_and_late_turn_context_never_backfill_ownership(
    monkeypatch,
) -> None:
    disabled_backend = _backend(monkeypatch, _settings(enabled=False))
    try:
        with lifecycle_execution(turn_context=_turn()):
            with disabled_backend.start_span("chat"):
                pass
        index, _epoch = _runtime_index_snapshot_for_tests()
        assert index.stats().traces == 0
    finally:
        disabled_backend.shutdown()

    _reset_trace_ownership_runtime_for_tests()
    enabled_backend = _backend(monkeypatch, _settings(enabled=True))
    try:
        with lifecycle_execution():
            root = enabled_backend.current_trace_ids()
            assert root.trace_id is not None
            apply_turn_context_to_current_agent_span(_turn())
            with enabled_backend.start_span("chat"):
                pass
        index, _epoch = _runtime_index_snapshot_for_tests()
        assert index.stats().traces == 0
    finally:
        enabled_backend.shutdown()


def test_phase4d_stale_backend_cannot_reset_current_ownership_index(
    monkeypatch,
) -> None:
    settings = _settings()
    backend_a = _backend(monkeypatch, settings)
    backend_b = _backend(monkeypatch, settings)
    current = {"backend": backend_a}
    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: current["backend"],
    )

    try:
        with lifecycle_execution(turn_context=_turn(room_id="old")):
            old_root = backend_a.current_trace_ids()
            assert old_root.trace_id is not None

        current["backend"] = backend_b
        with lifecycle_execution(turn_context=_turn(room_id="current")):
            current_root = backend_b.current_trace_ids()
            assert current_root.trace_id is not None
            assert current_root.span_id is not None

            # A stale worker may still hold the retired backend. Its span must be
            # inert for ownership and must not replace the authoritative epoch.
            with backend_a.start_span("retrieval"):
                pass
            with backend_b.start_span("chat"):
                current_chat = backend_b.current_trace_ids()

        snapshot = _snapshot(current_root.trace_id)
        assert snapshot is not None
        assert len(snapshot.segments) == 1
        segment = snapshot.segments[0]
        assert segment.room_id == "current"
        assert {(item.span_id, item.semantic_kind) for item in segment.owned_spans} == {
            (current_root.span_id, "invoke_agent"),
            (current_chat.span_id, "chat"),
        }
    finally:
        backend_a.shutdown()
        backend_b.shutdown()


def test_phase4d_backend_authority_is_rechecked_before_epoch_replacement(
    monkeypatch,
) -> None:
    class _Backend:
        enabled = True

    stale_backend = _Backend()
    current_backend = _Backend()
    current = {"backend": stale_backend}
    settings = _settings()
    stale_waiting = threading.Event()
    release_stale = threading.Event()
    stale_result: dict[str, object] = {}

    monkeypatch.setattr(
        "uagent.runtime.observability.bootstrap.get_observability_backend",
        lambda: current["backend"],
    )

    def get_settings() -> ObservabilitySettings:
        if threading.current_thread().name == "phase4d-stale-backend":
            stale_waiting.set()
            assert release_stale.wait(timeout=5.0)
        return settings

    monkeypatch.setattr(
        "uagent.runtime.observability.settings.get_observability_settings",
        get_settings,
    )

    def run_stale() -> None:
        stale_result["state"] = _runtime_state(stale_backend)

    stale_thread = threading.Thread(
        target=run_stale,
        name="phase4d-stale-backend",
    )
    stale_thread.start()
    assert stale_waiting.wait(timeout=5.0)

    current["backend"] = current_backend
    active, current_index, current_epoch = _runtime_state(current_backend)
    assert active is True
    handle = current_index.admit_segment(
        trace_id="1" * 32,
        root_span_id="2" * 16,
        principal_id="principal-1",
        room_id="room-1",
        project_id="project-1",
        service="uagent-test",
        entry_point="cli",
        private_session=False,
        server_bound_project=False,
    )
    assert handle is not None

    release_stale.set()
    stale_thread.join(timeout=5.0)
    assert not stale_thread.is_alive()

    final_index, final_epoch = _runtime_index_snapshot_for_tests()
    assert final_index is current_index
    assert final_epoch == current_epoch
    stale_state = stale_result["state"]
    assert isinstance(stale_state, tuple)
    assert stale_state[0] is False
    snapshot = current_index.lookup_segments(
        "1" * 32,
        deadline=time.monotonic() + 5.0,
    )
    assert snapshot is not None

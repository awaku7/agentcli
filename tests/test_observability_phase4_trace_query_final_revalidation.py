from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from uagent.runtime.identity_context import IdentityContext, IdentityResolutionError
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.observability.trace_ownership_index import TraceOwnershipIndex
from uagent.runtime.observability.trace_query_projection import (
    TraceBackendPage,
    TraceBackendSpanRecord,
    clear_trace_query_backend_adapter,
    install_trace_query_backend_adapter,
)
from uagent.web_impl import routes_observability
from uagent.web_impl.app import app

TRACE_ID = "1" * 32
ROOT_SPAN_ID = "2" * 16


def _valid_page(trace_id: str) -> TraceBackendPage:
    return TraceBackendPage(
        records=(
            TraceBackendSpanRecord(
                trace_id=trace_id,
                span_id=ROOT_SPAN_ID,
                parent_span_id=None,
                start_time=1_000,
                start_unit="ms",
                end_time=1_500,
                end_unit="ms",
                status="ok",
            ),
        ),
        decoded_bytes=64,
    )


class _RevokingAdapter:
    def __init__(self, revoked: dict[str, bool]):
        self._revoked = revoked

    def fetch_trace_page(
        self,
        *,
        trace_id,
        cursor,
        max_spans,
        max_decoded_bytes,
        deadline,
    ):
        del cursor, max_spans, max_decoded_bytes, deadline
        self._revoked["value"] = True
        return _valid_page(trace_id)


class _CountingAdapter:
    def __init__(self):
        self.calls = 0

    def fetch_trace_page(
        self,
        *,
        trace_id,
        cursor,
        max_spans,
        max_decoded_bytes,
        deadline,
    ):
        del cursor, max_spans, max_decoded_bytes, deadline
        self.calls += 1
        return _valid_page(trace_id)


class _ThreadRecordingAdapter:
    def __init__(self):
        self.thread_id: int | None = None

    def fetch_trace_page(
        self,
        *,
        trace_id,
        cursor,
        max_spans,
        max_decoded_bytes,
        deadline,
    ):
        del cursor, max_spans, max_decoded_bytes, deadline
        self.thread_id = threading.get_ident()
        return _valid_page(trace_id)


class _DeletingAdapter:
    def __init__(self, index: TraceOwnershipIndex, finished: dict[str, bool]):
        self._index = index
        self._finished = finished

    def fetch_trace_page(
        self,
        *,
        trace_id,
        cursor,
        max_spans,
        max_decoded_bytes,
        deadline,
    ):
        del cursor, max_spans, max_decoded_bytes, deadline
        assert self._index.delete_trace(trace_id) is True
        self._finished["value"] = True
        return _valid_page(trace_id)


@pytest.fixture(autouse=True)
def _clear_adapter_binding():
    clear_trace_query_backend_adapter()
    yield
    clear_trace_query_backend_adapter()


def _make_state():
    backend = type("Backend", (), {"enabled": True})()
    index = TraceOwnershipIndex()
    handle = index.admit_segment(
        trace_id=TRACE_ID,
        root_span_id=ROOT_SPAN_ID,
        principal_id="alice",
        room_id="",
        project_id="",
        service="uagent-test",
        entry_point="web",
        private_session=False,
        server_bound_project=False,
    )
    assert handle is not None
    state = routes_observability._TraceQueryIndexState(
        index=index,
        epoch=7,
        backend=backend,
    )
    return backend, index, state


def _configure_route(monkeypatch, *, backend, state) -> None:
    monkeypatch.setattr(
        routes_observability,
        "get_observability_settings",
        lambda: ObservabilitySettings(enabled=True, trace_query_enabled=True),
    )
    monkeypatch.setattr(
        routes_observability,
        "get_observability_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        routes_observability,
        "_request_identity",
        lambda _request: IdentityContext("alice", True, "oidc"),
    )
    monkeypatch.setattr(routes_observability, "_query_index_state", lambda: state)


def test_trace_query_revalidates_session_after_backend_retrieval(monkeypatch) -> None:
    backend, _, state = _make_state()
    revoked = {"value": False}
    install_trace_query_backend_adapter(
        backend=backend,
        adapter=_RevokingAdapter(revoked),
    )

    monkeypatch.setattr(
        routes_observability,
        "get_observability_settings",
        lambda: ObservabilitySettings(enabled=True, trace_query_enabled=True),
    )
    monkeypatch.setattr(
        routes_observability,
        "get_observability_backend",
        lambda: backend,
    )

    def identity(request):
        del request
        if revoked["value"]:
            raise IdentityResolutionError("session revoked")
        return IdentityContext("alice", True, "oidc")

    monkeypatch.setattr(routes_observability, "_request_identity", identity)
    monkeypatch.setattr(routes_observability, "_query_index_state", lambda: state)
    monkeypatch.setattr(
        routes_observability,
        "_query_index_state_is_current",
        lambda candidate: candidate is state,
    )

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")

    assert revoked["value"] is True
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def test_trace_query_does_not_fetch_after_generation_removal(monkeypatch) -> None:
    backend, index, state = _make_state()
    adapter = _CountingAdapter()
    install_trace_query_backend_adapter(backend=backend, adapter=adapter)
    _configure_route(monkeypatch, backend=backend, state=state)

    original_authorized_local_view = routes_observability._authorized_local_view
    removed = {"value": False}

    def authorize_then_remove(*args, **kwargs):
        view = original_authorized_local_view(*args, **kwargs)
        if view is not None and not removed["value"]:
            assert index.delete_trace(TRACE_ID) is True
            removed["value"] = True
        return view

    monkeypatch.setattr(
        routes_observability,
        "_authorized_local_view",
        authorize_then_remove,
    )

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")

    assert removed["value"] is True
    assert adapter.calls == 0
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def test_trace_query_does_not_fetch_after_epoch_replacement(monkeypatch) -> None:
    backend, index, state = _make_state()
    adapter = _CountingAdapter()
    install_trace_query_backend_adapter(backend=backend, adapter=adapter)
    _configure_route(monkeypatch, backend=backend, state=state)

    current_state = {"value": state}
    monkeypatch.setattr(
        routes_observability,
        "_query_index_state",
        lambda: current_state["value"],
    )
    original_authorized_local_view = routes_observability._authorized_local_view
    replaced = {"value": False}

    def authorize_then_replace(*args, **kwargs):
        view = original_authorized_local_view(*args, **kwargs)
        if view is not None and not replaced["value"]:
            current_state["value"] = routes_observability._TraceQueryIndexState(
                index=index,
                epoch=state.epoch + 1,
                backend=backend,
            )
            replaced["value"] = True
        return view

    monkeypatch.setattr(
        routes_observability,
        "_authorized_local_view",
        authorize_then_replace,
    )

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")

    assert replaced["value"] is True
    assert adapter.calls == 0
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def test_trace_query_backend_projection_runs_off_event_loop(monkeypatch) -> None:
    backend, _, state = _make_state()
    adapter = _ThreadRecordingAdapter()
    install_trace_query_backend_adapter(backend=backend, adapter=adapter)
    _configure_route(monkeypatch, backend=backend, state=state)

    original_authorized_local_view = routes_observability._authorized_local_view
    route_thread = {"value": None}
    authorization_threads = []

    def record_event_loop():
        route_thread["value"] = threading.get_ident()
        return True

    monkeypatch.setattr(routes_observability, "_feature_enabled", record_event_loop)

    def record_route_thread(*args, **kwargs):
        authorization_threads.append(threading.get_ident())
        return original_authorized_local_view(*args, **kwargs)

    monkeypatch.setattr(
        routes_observability,
        "_authorized_local_view",
        record_route_thread,
    )

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")

    assert response.status_code == 200
    assert route_thread["value"] is not None
    assert adapter.thread_id is not None
    assert adapter.thread_id != route_thread["value"]
    assert len(authorization_threads) == 2
    assert all(thread != route_thread["value"] for thread in authorization_threads)


def test_trace_query_generation_removal_beats_backend_timeout(monkeypatch) -> None:
    backend, index, state = _make_state()
    finished = {"value": False}
    install_trace_query_backend_adapter(
        backend=backend,
        adapter=_DeletingAdapter(index, finished),
    )
    _configure_route(monkeypatch, backend=backend, state=state)
    monkeypatch.setattr(
        routes_observability,
        "_deadline_alive",
        lambda _deadline: not finished["value"],
    )

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")

    assert finished["value"] is True
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}


def _request():
    return Request(
        {"type": "http", "http_version": "1.1", "headers": [], "query_string": b""}
    )


@pytest.mark.parametrize("phase", ["initial", "backend", "final"])
@pytest.mark.parametrize("invalidation", [None, "generation", "epoch"])
def test_stalled_worker_obeys_deadline_and_ownership_precedence(
    monkeypatch, phase, invalidation
) -> None:
    backend, index, state = _make_state()
    _configure_route(monkeypatch, backend=backend, state=state)
    monkeypatch.setattr(routes_observability, "_TRACE_QUERY_DEADLINE_SECONDS", 0.25)
    entered = threading.Event()
    release = threading.Event()
    calls = []
    deadlines = []
    original = routes_observability._authorized_local_view

    def stall():
        if invalidation == "generation":
            assert index.delete_trace(TRACE_ID)
        elif invalidation == "epoch":
            monkeypatch.setattr(
                routes_observability,
                "_query_index_state",
                lambda: routes_observability._TraceQueryIndexState(
                    index=index, epoch=state.epoch + 1, backend=backend
                ),
            )
        entered.set()
        assert release.wait(3)

    def authorize(*args, **kwargs):
        calls.append("authorization")
        deadlines.append(kwargs["deadline"])
        if (phase == "initial" and len(calls) == 1) or (
            phase == "final" and len(calls) == 3
        ):
            stall()
        return original(*args, **kwargs)

    class Adapter:
        def fetch_trace_page(self, *, trace_id, deadline, **kwargs):
            calls.append("backend")
            deadlines.append(deadline)
            if phase == "backend":
                stall()
            return _valid_page(trace_id)

    monkeypatch.setattr(routes_observability, "_authorized_local_view", authorize)
    install_trace_query_backend_adapter(backend=backend, adapter=Adapter())

    async def scenario():
        task = asyncio.create_task(
            routes_observability.get_observability_trace(TRACE_ID, _request())
        )
        try:
            # This coroutine must keep progressing while synchronous work stalls.
            async with asyncio.timeout(1):
                while not entered.is_set():
                    await asyncio.sleep(0.001)
                response = await task
            assert not release.is_set()
            expected = 404 if invalidation else 503
            assert response.status_code == expected
            assert json.loads(response.body) == {
                "error": (
                    "trace_not_found" if invalidation else "trace_query_unavailable"
                )
            }
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    assert len(set(deadlines)) == 1
    assert (
        calls
        == {
            "initial": ["authorization"],
            "backend": ["authorization", "backend"],
            "final": ["authorization", "backend", "authorization"],
        }[phase]
    )


@pytest.mark.parametrize("queued_pass", [1, 2, 3])
def test_executor_queue_wait_uses_shared_deadline(monkeypatch, queued_pass) -> None:
    backend, _, state = _make_state()
    _configure_route(monkeypatch, backend=backend, state=state)
    monkeypatch.setattr(routes_observability, "_TRACE_QUERY_DEADLINE_SECONDS", 0.25)
    adapter = _CountingAdapter()
    install_trace_query_backend_adapter(backend=backend, adapter=adapter)
    release = threading.Event()
    entered = threading.Event()
    work_calls = []
    original_to_thread = asyncio.to_thread

    def occupy_executor():
        entered.set()
        assert release.wait(3)

    async def scenario():
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        loop.set_default_executor(executor)
        passes = 0

        async def queue_worker(function, *args, **kwargs):
            nonlocal passes
            passes += 1
            if passes == queued_pass:
                executor.submit(occupy_executor)
                while not entered.is_set():
                    await asyncio.sleep(0.001)

            def record_work():
                work_calls.append(passes)
                return function(*args, **kwargs)

            return await original_to_thread(record_work)

        monkeypatch.setattr(asyncio, "to_thread", queue_worker)
        try:
            response = await asyncio.wait_for(
                routes_observability.get_observability_trace(TRACE_ID, _request()), 1
            )
            assert entered.is_set()
            assert not release.is_set()
            assert response.status_code == 503
            assert json.loads(response.body) == {"error": "trace_query_unavailable"}
        finally:
            release.set()

    asyncio.run(scenario())
    # Cancelled queued work must never contact the adapter later.
    assert len(work_calls) == queued_pass - 1
    assert adapter.calls == (1 if queued_pass == 3 else 0)


@pytest.mark.parametrize("invalidation", ["generation", "epoch"])
def test_ownership_change_while_backend_is_queued_prevents_fetch(
    monkeypatch, invalidation
) -> None:
    backend, index, state = _make_state()
    _configure_route(monkeypatch, backend=backend, state=state)
    adapter = _CountingAdapter()
    install_trace_query_backend_adapter(backend=backend, adapter=adapter)
    original_to_thread = asyncio.to_thread
    passes = 0

    async def invalidate_before_worker_starts(function, *args, **kwargs):
        nonlocal passes
        passes += 1
        if passes == 2:
            if invalidation == "generation":
                assert index.delete_trace(TRACE_ID)
            else:
                monkeypatch.setattr(
                    routes_observability,
                    "_query_index_state",
                    lambda: routes_observability._TraceQueryIndexState(
                        index=index, epoch=state.epoch + 1, backend=backend
                    ),
                )
        return await original_to_thread(function, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", invalidate_before_worker_starts)
    response = asyncio.run(
        routes_observability.get_observability_trace(TRACE_ID, _request())
    )
    assert passes == 2
    assert adapter.calls == 0
    assert response.status_code == 404
    assert json.loads(response.body) == {"error": "trace_not_found"}


def test_trace_query_generation_removal_after_final_auth_beats_timeout(
    monkeypatch,
) -> None:
    backend, index, state = _make_state()
    adapter = _CountingAdapter()
    install_trace_query_backend_adapter(backend=backend, adapter=adapter)
    _configure_route(monkeypatch, backend=backend, state=state)

    original_authorized_local_view = routes_observability._authorized_local_view
    authorization_calls = {"value": 0}
    finished = {"value": False}

    def authorize_then_remove_on_final(*args, **kwargs):
        view = original_authorized_local_view(*args, **kwargs)
        authorization_calls["value"] += 1
        if authorization_calls["value"] == 2:
            assert index.delete_trace(TRACE_ID) is True
            finished["value"] = True
        return view

    monkeypatch.setattr(
        routes_observability,
        "_authorized_local_view",
        authorize_then_remove_on_final,
    )
    monkeypatch.setattr(
        routes_observability,
        "_deadline_alive",
        lambda _deadline: not finished["value"],
    )

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")

    assert adapter.calls == 1
    assert authorization_calls["value"] == 2
    assert finished["value"] is True
    assert response.status_code == 404
    assert response.json() == {"error": "trace_not_found"}

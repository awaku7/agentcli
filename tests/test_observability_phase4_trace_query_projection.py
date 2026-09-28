from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from uagent.runtime.identity_context import IdentityContext
from uagent.runtime.observability.settings import ObservabilitySettings
from uagent.runtime.observability.trace_ownership_index import TraceOwnershipIndex
from uagent.runtime.observability.trace_query_projection import (
    MAX_BACKEND_DECODED_BYTES,
    TraceBackendPage,
    TraceBackendSpanRecord,
    clear_trace_query_backend_adapter,
    get_trace_query_backend_adapter,
    install_trace_query_backend_adapter,
    project_trace_view,
)
from uagent.web_impl import routes_observability
from uagent.web_impl.app import app

TRACE_ID = "1" * 32
ROOT_SPAN_ID = "2" * 16
CHILD_SPAN_ID = "3" * 16
REMOTE_SPAN_ID = "4" * 16


class _PagedAdapter:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def fetch_trace_page(
        self,
        *,
        trace_id,
        cursor,
        max_spans,
        max_decoded_bytes,
        deadline,
    ):
        self.calls.append(
            {
                "trace_id": trace_id,
                "cursor": cursor,
                "max_spans": max_spans,
                "max_decoded_bytes": max_decoded_bytes,
                "deadline": deadline,
            }
        )
        if not self.pages:
            return TraceBackendPage(records=(), decoded_bytes=0)
        return self.pages.pop(0)


@pytest.fixture(autouse=True)
def _clear_adapter_binding():
    clear_trace_query_backend_adapter()
    yield
    clear_trace_query_backend_adapter()


def _record(
    span_id,
    *,
    parent_span_id=None,
    trace_id=TRACE_ID,
    start_time=1_000,
    start_unit="ms",
    end_time=1_500,
    end_unit="ms",
    status=None,
):
    return TraceBackendSpanRecord(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        start_time=start_time,
        start_unit=start_unit,
        end_time=end_time,
        end_unit=end_unit,
        status=status,
    )


def _deadline():
    return time.monotonic() + 5.0


def test_projection_emits_only_closed_schema_and_indexed_semantics() -> None:
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=(
                    _record(
                        CHILD_SPAN_ID,
                        parent_span_id=ROOT_SPAN_ID,
                        start_time=1_200_000,
                        start_unit="us",
                        end_time=1_500_000_000,
                        end_unit="ns",
                        status=" completed ",
                    ),
                    _record(ROOT_SPAN_ID, status="failure"),
                ),
                decoded_bytes=256,
            )
        ]
    )

    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=(
            (ROOT_SPAN_ID, "invoke_agent"),
            (CHILD_SPAN_ID, "chat"),
        ),
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is not None
    assert projection.as_json() == {
        "schema_version": "uag.trace_view.v1",
        "trace_id": TRACE_ID,
        "partial": False,
        "spans": [
            {
                "span_id": ROOT_SPAN_ID,
                "parent_omitted": False,
                "name": "AGENT",
                "start_time": 1000,
                "end_time": 1500,
                "duration_ms": 500,
                "status_code": "ERROR",
            },
            {
                "span_id": CHILD_SPAN_ID,
                "parent_omitted": False,
                "parent_span_id": ROOT_SPAN_ID,
                "name": "LLM",
                "start_time": 1200,
                "end_time": 1500,
                "duration_ms": 300,
                "status_code": "OK",
            },
        ],
    }


def test_projection_omits_duplicate_records_and_marks_parent_omitted() -> None:
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=(
                    _record(ROOT_SPAN_ID),
                    _record(ROOT_SPAN_ID, start_time=900),
                    _record(CHILD_SPAN_ID, parent_span_id=ROOT_SPAN_ID),
                ),
                decoded_bytes=128,
            )
        ]
    )
    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=(
            (ROOT_SPAN_ID, "invoke_agent"),
            (CHILD_SPAN_ID, "chat"),
        ),
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is not None
    payload = projection.as_json()
    assert payload["partial"] is True
    assert payload["spans"] == [
        {
            "span_id": CHILD_SPAN_ID,
            "parent_omitted": True,
            "name": "LLM",
            "start_time": 1000,
            "end_time": 1500,
            "duration_ms": 500,
            "status_code": "UNSET",
        }
    ]


def test_projection_filters_mismatched_trace_and_unowned_spans() -> None:
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=(
                    _record(ROOT_SPAN_ID),
                    _record(CHILD_SPAN_ID, trace_id="a" * 32),
                    _record(REMOTE_SPAN_ID),
                ),
                decoded_bytes=128,
            )
        ]
    )
    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=((ROOT_SPAN_ID, "invoke_agent"),),
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is not None
    payload = projection.as_json()
    assert payload["partial"] is True
    assert [item["span_id"] for item in payload["spans"]] == [ROOT_SPAN_ID]


def test_projection_rejects_textual_and_raw_reversed_timing() -> None:
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=(
                    _record(ROOT_SPAN_ID, start_time="1000"),
                    _record(
                        CHILD_SPAN_ID,
                        start_time=1_000_999,
                        start_unit="us",
                        end_time=1_000_998_000,
                        end_unit="ns",
                    ),
                ),
                decoded_bytes=128,
            )
        ]
    )
    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=(
            (ROOT_SPAN_ID, "invoke_agent"),
            (CHILD_SPAN_ID, "chat"),
        ),
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is not None
    assert projection.partial is True
    assert projection.spans == ()


def test_projection_malformed_status_maps_to_unset_without_partial() -> None:
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=(_record(ROOT_SPAN_ID, status="x" * 17),),
                decoded_bytes=64,
            )
        ]
    )
    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=((ROOT_SPAN_ID, "unknown"),),
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is not None
    assert projection.partial is False
    assert projection.spans[0]["name"] == "UNKNOWN"
    assert projection.spans[0]["status_code"] == "UNSET"


def test_projection_stops_at_decoded_byte_ceiling_with_safe_partial() -> None:
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=(_record(ROOT_SPAN_ID),),
                decoded_bytes=MAX_BACKEND_DECODED_BYTES,
                next_cursor="next",
            )
        ]
    )
    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=((ROOT_SPAN_ID, "invoke_agent"),),
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is not None
    assert projection.partial is True
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["max_decoded_bytes"] == MAX_BACKEND_DECODED_BYTES


def test_projection_rejects_adapter_page_that_exceeds_requested_span_cap() -> None:
    records = tuple(_record(f"{index + 1:016x}") for index in range(501))
    adapter = _PagedAdapter([TraceBackendPage(records=records, decoded_bytes=1024)])
    authorized = tuple((record.span_id, "internal") for record in records)

    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=authorized,
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is None


def test_projection_caps_output_at_500_and_orders_by_start_then_span_id() -> None:
    all_records = tuple(
        _record(
            f"{index + 1:016x}",
            start_time=2000 - index,
            end_time=3000,
        )
        for index in range(501)
    )
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=all_records[:500],
                decoded_bytes=1000,
                next_cursor="page-2",
            ),
            TraceBackendPage(records=all_records[500:], decoded_bytes=10),
        ]
    )
    authorized = tuple((record.span_id, "internal") for record in all_records)

    projection = project_trace_view(
        adapter,
        trace_id=TRACE_ID,
        authorized_span_kinds=authorized,
        initial_partial=False,
        deadline=_deadline(),
    )

    assert projection is not None
    assert projection.partial is True
    assert len(projection.spans) == 500
    ordering = [(item["start_time"], item["span_id"]) for item in projection.spans]
    assert ordering == sorted(ordering)


def test_adapter_binding_is_exact_backend_identity() -> None:
    backend = type("Backend", (), {})()
    other_backend = type("Backend", (), {})()
    adapter = _PagedAdapter([])

    install_trace_query_backend_adapter(backend=backend, adapter=adapter)
    assert get_trace_query_backend_adapter(backend) is adapter
    assert get_trace_query_backend_adapter(other_backend) is None

    clear_trace_query_backend_adapter(backend=other_backend)
    assert get_trace_query_backend_adapter(backend) is adapter
    clear_trace_query_backend_adapter(backend=backend)
    assert get_trace_query_backend_adapter(backend) is None


def test_route_returns_successful_closed_projection_when_adapter_is_bound(
    monkeypatch,
) -> None:
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
    adapter = _PagedAdapter(
        [
            TraceBackendPage(
                records=(_record(ROOT_SPAN_ID, status="ok"),),
                decoded_bytes=64,
            )
        ]
    )
    install_trace_query_backend_adapter(backend=backend, adapter=adapter)

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
        lambda request: IdentityContext("alice", True, "oidc"),
    )
    monkeypatch.setattr(
        routes_observability,
        "_query_index_state",
        lambda: state,
    )
    monkeypatch.setattr(
        routes_observability,
        "_query_index_state_is_current",
        lambda candidate: candidate is state,
    )

    response = TestClient(app).get(f"/api/observability/traces/{TRACE_ID}")
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "uag.trace_view.v1",
        "trace_id": TRACE_ID,
        "partial": False,
        "spans": [
            {
                "span_id": ROOT_SPAN_ID,
                "parent_omitted": False,
                "name": "AGENT",
                "start_time": 1000,
                "end_time": 1500,
                "duration_ms": 500,
                "status_code": "OK",
            }
        ],
    }

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture(autouse=True)
def _clear_adapter_binding():
    clear_trace_query_backend_adapter()
    yield
    clear_trace_query_backend_adapter()


def test_trace_query_revalidates_session_after_backend_retrieval(monkeypatch) -> None:
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

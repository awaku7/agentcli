"""Authorization-aware ordinary-user observability routes."""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from ..runtime.identity_context import IdentityContext
from ..runtime.memory_access import MemoryAccessError
from ..runtime.observability.bootstrap import get_observability_backend
from ..runtime.observability.settings import get_observability_settings
from ..runtime.observability.trace_ownership_index import (
    MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE,
    MAX_LOCAL_SCOPE_TEXT_CHARS,
    MAX_LOCAL_SEGMENTS_PER_TRACE,
    LocalSegmentSnapshot,
    OwnedSpanSnapshot,
    TraceOwnershipIndex,
    TraceOwnershipSnapshot,
)
from ..runtime.observability.trace_ownership_runtime import _runtime_state
from ..runtime.observability.trace_query_projection import (
    get_trace_query_backend_adapter,
    project_trace_view,
)
from ..runtime.project_access import ProjectAccessPolicy
from ..runtime.room_access import RoomAccessPolicy
from .app import app
from .routes_api import _memory_error, _memory_store, _project_id, _request_identity

_TRACE_QUERY_DEADLINE_SECONDS = 5.0
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
_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class _TraceQueryIndexState:
    index: TraceOwnershipIndex
    epoch: int
    backend: object | None = None


@dataclass(frozen=True)
class _AuthorizedLocalView:
    span_kinds: tuple[tuple[str, str], ...]
    partial: bool


def _json_error(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": code})


def _feature_enabled() -> bool:
    try:
        settings = get_observability_settings()
        if settings.enabled is not True or settings.trace_query_enabled is not True:
            return False
        backend = get_observability_backend()
        return backend.enabled is True
    except Exception:
        return False


def _query_index_state() -> _TraceQueryIndexState | None:
    try:
        backend = get_observability_backend()
        active, index, epoch = _runtime_state(backend)
    except Exception:
        return None
    if not active:
        return None
    return _TraceQueryIndexState(backend=backend, index=index, epoch=epoch)


def _query_index_state_is_current(state: object) -> bool:
    if type(state) is not _TraceQueryIndexState:
        return False
    current = _query_index_state()
    return bool(
        current is not None
        and current.backend is state.backend
        and current.index is state.index
        and current.epoch == state.epoch
    )


def _deadline_alive(deadline: float) -> bool:
    try:
        now = time.monotonic()
    except Exception:
        return False
    return type(now) in {int, float} and not isinstance(now, bool) and now < deadline


def _generation_is_live_for_result(
    state: _TraceQueryIndexState,
    *,
    trace_id: str,
    generation: int,
) -> bool:
    """Classify ownership invalidation without letting request timeout mask it.

    This check is local-only and does not extend backend or authorization work.
    The route still rejects an otherwise-live generation with 503 once the shared
    request deadline has expired.
    """

    return state.index.generation_is_live(
        trace_id=trace_id,
        generation=generation,
        deadline=sys.float_info.max,
    )


def _ascii_header_name_is(value: object, expected: bytes) -> bool:
    """Compare one ASGI header name case-insensitively without allocating a copy."""

    if type(value) is not bytes or len(value) != len(expected):
        return False
    for actual, wanted in zip(value, expected):
        if 65 <= actual <= 90:
            actual += 32
        if actual != wanted:
            return False
    return True


def _request_shape_is_valid(request: Request, *, deadline: float) -> bool:
    if not _deadline_alive(deadline):
        return False

    scope = request.scope
    raw_query = scope.get("query_string", b"")
    if type(raw_query) is not bytes or raw_query:
        return False

    raw_headers = scope.get("headers", ())
    if type(raw_headers) not in {list, tuple}:
        return False

    content_lengths: list[bytes] = []
    for item in raw_headers:
        if not _deadline_alive(deadline):
            return False
        if type(item) is not tuple or len(item) != 2:
            return False
        name, value = item
        if type(name) is not bytes or type(value) is not bytes:
            return False
        if _ascii_header_name_is(name, b"transfer-encoding"):
            return False
        if _ascii_header_name_is(name, b"content-length"):
            content_lengths.append(value)
            if len(content_lengths) > 1:
                return False

    if content_lengths:
        value = content_lengths[0]
        if not 1 <= len(value) <= 20:
            return False
        if any(character < 48 or character > 57 for character in value):
            return False
        if len(value) > 1 and value.startswith(b"0"):
            return False
        if value != b"0":
            return False
        return _deadline_alive(deadline)

    # HTTP/1.x request framing proves an empty request body when neither
    # Transfer-Encoding nor Content-Length is present. ASGI does not provide a
    # size-limited receive primitive for HTTP/2/3, so the v1 route fails closed
    # there unless Content-Length: 0 already proves emptiness.
    http_version = scope.get("http_version")
    return bool(http_version in {"1.0", "1.1"} and _deadline_alive(deadline))


def _valid_trace_id(value: object) -> bool:
    return bool(
        type(value) is str
        and len(value) == 32
        and value != "0" * 32
        and all(character in _HEX for character in value)
    )


def _valid_span_id(value: object) -> bool:
    return bool(
        type(value) is str
        and len(value) == 16
        and value != "0" * 16
        and all(character in _HEX for character in value)
    )


def _valid_scope_text(value: object) -> bool:
    return type(value) is str and len(value) <= MAX_LOCAL_SCOPE_TEXT_CHARS


def _snapshot_is_well_formed(
    snapshot: object,
    *,
    requested_trace_id: str,
) -> bool:
    if type(snapshot) is not TraceOwnershipSnapshot:
        return False
    if snapshot.trace_id != requested_trace_id:
        return False
    if type(snapshot.generation) is not int or snapshot.generation <= 0:
        return False
    if type(snapshot.segments) is not tuple:
        return False
    if not 1 <= len(snapshot.segments) <= MAX_LOCAL_SEGMENTS_PER_TRACE:
        return False

    seen_span_ids: set[str] = set()
    total_spans = 0
    for segment in snapshot.segments:
        if type(segment) is not LocalSegmentSnapshot:
            return False
        if not _valid_span_id(segment.root_span_id):
            return False
        scope_values = (
            segment.principal_id,
            segment.room_id,
            segment.project_id,
            segment.service,
            segment.entry_point,
        )
        if not all(_valid_scope_text(value) for value in scope_values):
            return False
        if not segment.principal_id or not segment.service or not segment.entry_point:
            return False
        if type(segment.private_session) is not bool:
            return False
        if type(segment.server_bound_project) is not bool:
            return False
        if type(segment.owned_spans) is not tuple or not segment.owned_spans:
            return False

        root_kind: str | None = None
        for owned in segment.owned_spans:
            if type(owned) is not OwnedSpanSnapshot:
                return False
            if not _valid_span_id(owned.span_id):
                return False
            if type(owned.semantic_kind) is not str:
                return False
            if owned.semantic_kind not in _SEMANTIC_KINDS:
                return False
            if owned.span_id in seen_span_ids:
                return False
            seen_span_ids.add(owned.span_id)
            total_spans += 1
            if total_spans > MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE:
                return False
            if owned.span_id == segment.root_span_id:
                root_kind = owned.semantic_kind
        if root_kind != "invoke_agent":
            return False
    return True


def _revalidate_query_identity(
    request: Request,
    *,
    initial_identity: IdentityContext,
) -> IdentityContext | None:
    """Revalidate live authentication without allowing principal/kind switching."""

    try:
        current = _request_identity(request)
    except Exception:
        return None
    if type(current) is not IdentityContext or not current.authenticated:
        return None
    if current.principal_id != initial_identity.principal_id:
        return None
    if current.authn_kind != initial_identity.authn_kind:
        return None
    return current


def _segment_is_authorized(
    segment: LocalSegmentSnapshot,
    *,
    identity: IdentityContext,
    request: Request,
    room_policy: RoomAccessPolicy | None,
    project_policy: ProjectAccessPolicy | None,
) -> bool:
    # One Web turn is one principal-owned logical trace. Shared room/project
    # membership never grants another principal access to that turn's trace.
    if identity.principal_id != segment.principal_id:
        return False

    if segment.room_id:
        if room_policy is None or project_policy is None:
            raise RuntimeError("room/project policy is unavailable")
        private_owner = room_policy.private_room_owner(segment.room_id)
        current_private = private_owner is not None
        if current_private != segment.private_session:
            return False
        if current_private:
            if not room_policy.is_private_room_for(
                identity.principal_id, segment.room_id
            ):
                return False
        elif room_policy.membership(identity.principal_id, segment.room_id) is None:
            return False

        current_project = project_policy.room_project(segment.room_id) or ""
        if current_project != segment.project_id:
            return False
        if bool(current_project) != segment.server_bound_project:
            return False
        if current_project and not project_policy.can_access(
            identity.principal_id, current_project, "viewer"
        ):
            return False
        return True

    if segment.private_session:
        return False

    if segment.project_id:
        if project_policy is None:
            raise RuntimeError("project policy is unavailable")
        if not project_policy.can_access(
            identity.principal_id, segment.project_id, "viewer"
        ):
            return False
        if segment.server_bound_project:
            try:
                return _project_id(segment.project_id, request) == segment.project_id
            except MemoryAccessError:
                return False
        return True

    return not segment.server_bound_project


def _authorized_local_view(
    snapshot: TraceOwnershipSnapshot,
    *,
    identity: IdentityContext,
    request: Request,
    deadline: float,
) -> _AuthorizedLocalView | None:
    if type(identity) is not IdentityContext or not identity.authenticated:
        return None

    needs_store = any(
        segment.room_id or segment.project_id for segment in snapshot.segments
    )
    has_project_scope = any(segment.project_id for segment in snapshot.segments)
    store = None
    room_policy = None
    project_policy = None
    synced_identity: IdentityContext | None = None
    try:
        if needs_store:
            store = _memory_store()
            room_policy = RoomAccessPolicy(store)
            project_policy = ProjectAccessPolicy(store)

        authorized_segments = 0
        filtered_segments = 0
        authorized_span_kinds: list[tuple[str, str]] = []
        for segment in snapshot.segments:
            if not _deadline_alive(deadline):
                return None
            current_identity = _revalidate_query_identity(
                request,
                initial_identity=identity,
            )
            if current_identity is None:
                return None
            if project_policy is not None and has_project_scope:
                if current_identity != synced_identity:
                    project_policy.sync_directory_policy(current_identity)
                    synced_identity = current_identity
                    if not _deadline_alive(deadline):
                        return None

            segment_authorized = _segment_is_authorized(
                segment,
                identity=current_identity,
                request=request,
                room_policy=room_policy,
                project_policy=project_policy,
            )
            if not _deadline_alive(deadline):
                return None

            if segment_authorized:
                authorized_segments += 1
            else:
                filtered_segments += 1

            for owned in segment.owned_spans:
                if not _deadline_alive(deadline):
                    return None
                span_identity = _revalidate_query_identity(
                    request,
                    initial_identity=identity,
                )
                if span_identity is None:
                    return None
                if project_policy is not None and span_identity != synced_identity:
                    project_policy.sync_directory_policy(span_identity)
                    synced_identity = span_identity
                    if not _deadline_alive(deadline):
                        return None
                span_authorized = _segment_is_authorized(
                    segment,
                    identity=span_identity,
                    request=request,
                    room_policy=room_policy,
                    project_policy=project_policy,
                )
                if not _deadline_alive(deadline):
                    return None
                # A scope decision that changes while this bounded lookup is in
                # flight cannot be treated as a complete authorization view.
                if span_authorized != segment_authorized:
                    return None
                if span_authorized:
                    authorized_span_kinds.append((owned.span_id, owned.semantic_kind))
                    if len(authorized_span_kinds) > MAX_LOCAL_OWNED_SPAN_IDS_PER_TRACE:
                        return None

        if authorized_segments <= 0 or not authorized_span_kinds:
            return None
        return _AuthorizedLocalView(
            span_kinds=tuple(authorized_span_kinds),
            partial=filtered_segments > 0,
        )
    except Exception:
        return None
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                pass


@app.get("/api/observability/traces/{trace_id}")
async def get_observability_trace(trace_id: str, request: Request):
    """Return one bounded authorization-aware ordinary-user trace projection."""

    if not _feature_enabled():
        return _json_error(404, "not_found")

    try:
        identity = _request_identity(request)
    except Exception as exc:
        return _memory_error(exc)

    try:
        started = time.monotonic()
        if type(started) not in {int, float} or isinstance(started, bool):
            raise RuntimeError("invalid monotonic clock")
        deadline = float(started) + _TRACE_QUERY_DEADLINE_SECONDS
    except Exception:
        return _json_error(400, "invalid_request")

    if not _request_shape_is_valid(request, deadline=deadline):
        return _json_error(400, "invalid_request")

    if not _valid_trace_id(trace_id):
        return _json_error(400, "invalid_trace_id")

    state = _query_index_state()
    if state is None:
        return _json_error(404, "trace_not_found")
    snapshot = state.index.lookup_segments(
        trace_id,
        max_segments=MAX_LOCAL_SEGMENTS_PER_TRACE,
        deadline=deadline,
    )
    if not _snapshot_is_well_formed(snapshot, requested_trace_id=trace_id):
        return _json_error(404, "trace_not_found")
    assert snapshot is not None

    local_view = _authorized_local_view(
        snapshot,
        identity=identity,
        request=request,
        deadline=deadline,
    )
    if local_view is None:
        return _json_error(404, "trace_not_found")

    # Revalidate ownership immediately before any backend adapter access. A stale
    # epoch/backend/index or removed generation must never reach the backend.
    if not _deadline_alive(deadline):
        return _json_error(503, "trace_query_unavailable")
    if not _query_index_state_is_current(state):
        return _json_error(404, "trace_not_found")
    if not state.index.generation_is_live(
        trace_id=trace_id,
        generation=snapshot.generation,
        deadline=deadline,
    ):
        return _json_error(404, "trace_not_found")
    if not _deadline_alive(deadline):
        return _json_error(503, "trace_query_unavailable")

    adapter = get_trace_query_backend_adapter(state.backend)
    if not _query_index_state_is_current(state):
        return _json_error(404, "trace_not_found")
    if not state.index.generation_is_live(
        trace_id=trace_id,
        generation=snapshot.generation,
        deadline=deadline,
    ):
        return _json_error(404, "trace_not_found")
    if not _deadline_alive(deadline):
        return _json_error(503, "trace_query_unavailable")

    projection = None
    if adapter is not None:
        projection = await asyncio.to_thread(
            project_trace_view,
            adapter,
            trace_id=trace_id,
            authorized_span_kinds=local_view.span_kinds,
            initial_partial=local_view.partial,
            deadline=deadline,
        )

    # Ownership invalidation has precedence over backend success/failure/timeout.
    if not _query_index_state_is_current(state):
        return _json_error(404, "trace_not_found")
    if not _generation_is_live_for_result(
        state,
        trace_id=trace_id,
        generation=snapshot.generation,
    ):
        return _json_error(404, "trace_not_found")
    if not _deadline_alive(deadline):
        return _json_error(503, "trace_query_unavailable")

    if projection is not None:
        final_local_view = _authorized_local_view(
            snapshot,
            identity=identity,
            request=request,
            deadline=deadline,
        )
        if not _query_index_state_is_current(state):
            return _json_error(404, "trace_not_found")
        if not _generation_is_live_for_result(
            state,
            trace_id=trace_id,
            generation=snapshot.generation,
        ):
            return _json_error(404, "trace_not_found")
        if not _deadline_alive(deadline):
            return _json_error(503, "trace_query_unavailable")
        if final_local_view is None or final_local_view != local_view:
            return _json_error(404, "trace_not_found")

    if not _query_index_state_is_current(state):
        return _json_error(404, "trace_not_found")
    if not _generation_is_live_for_result(
        state,
        trace_id=trace_id,
        generation=snapshot.generation,
    ):
        return _json_error(404, "trace_not_found")
    if not _deadline_alive(deadline):
        return _json_error(503, "trace_query_unavailable")

    if projection is None:
        return _json_error(503, "trace_query_unavailable")
    return JSONResponse(status_code=200, content=projection.as_json())


__all__ = ["get_observability_trace"]

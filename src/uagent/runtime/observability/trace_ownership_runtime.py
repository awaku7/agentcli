"""Trusted runtime binding for the Phase 4D local trace-ownership index."""

from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any

from .api import ObservabilityBackend, ObservabilitySpan
from .trace_ownership_index import TraceAdmissionHandle, TraceOwnershipIndex

if TYPE_CHECKING:
    from ..identity_context import TurnContext


@dataclass(frozen=True)
class TraceOwnershipBinding:
    """One live process-local ownership generation bound to a runtime context."""

    index: TraceOwnershipIndex
    epoch: int
    handle: TraceAdmissionHandle


_STATE_LOCK = threading.Lock()
_INDEX = TraceOwnershipIndex()
_EPOCH = 0
_BACKEND: object | None = None
_SETTINGS: object | None = None
_CURRENT_BINDING: ContextVar[TraceOwnershipBinding | None] = ContextVar(
    "uagent_trace_ownership_binding", default=None
)


def _runtime_state(
    backend: ObservabilityBackend,
) -> tuple[bool, TraceOwnershipIndex, int]:
    """Return the active index epoch for the authoritative process backend."""

    global _INDEX, _EPOCH, _BACKEND, _SETTINGS

    try:
        from .bootstrap import get_observability_backend

        if get_observability_backend() is not backend:
            with _STATE_LOCK:
                return False, _INDEX, _EPOCH
    except Exception:
        with _STATE_LOCK:
            return False, _INDEX, _EPOCH

    try:
        from .settings import get_observability_settings

        settings = get_observability_settings()
    except Exception:
        settings = None

    with _STATE_LOCK:
        try:
            if get_observability_backend() is not backend:
                return False, _INDEX, _EPOCH
            settings = get_observability_settings()
            active = bool(
                backend.enabled
                and settings.enabled is True
                and settings.trace_query_enabled is True
            )
        except Exception:
            return False, _INDEX, _EPOCH

        if backend is not _BACKEND or settings is not _SETTINGS:
            _INDEX = TraceOwnershipIndex()
            _EPOCH += 1
            _BACKEND = backend
            _SETTINGS = settings
        return active, _INDEX, _EPOCH


def mask_current_trace_ownership() -> Any:
    """Mask any parent binding while a new canonical Agent root is created."""

    return _CURRENT_BINDING.set(None)


def bind_current_trace_ownership(binding: TraceOwnershipBinding | None) -> Any:
    """Bind one admitted local segment for child-span ownership registration."""

    return _CURRENT_BINDING.set(binding)


def reset_current_trace_ownership(token: Any) -> None:
    """Restore the previous runtime ownership binding without affecting execution."""

    try:
        _CURRENT_BINDING.reset(token)
    except Exception:
        pass


@contextmanager
def masked_trace_ownership_scope() -> Iterator[None]:
    """Mask a parent segment while a new canonical Agent root is created."""

    token = mask_current_trace_ownership()
    try:
        yield
    finally:
        reset_current_trace_ownership(token)


@contextmanager
def bound_trace_ownership_scope(
    binding: TraceOwnershipBinding | None,
) -> Iterator[None]:
    """Bind one admitted segment for the lifetime of its canonical Agent span."""

    token = bind_current_trace_ownership(binding)
    try:
        yield
    finally:
        reset_current_trace_ownership(token)


def _service_name(backend: ObservabilityBackend) -> str | None:
    direct = getattr(backend, "service_name", None)
    if type(direct) is str:
        return direct

    try:
        provider = getattr(backend, "_provider", None)
        resource = getattr(provider, "resource", None)
        attributes = getattr(resource, "attributes", None)
        if isinstance(attributes, Mapping):
            value = attributes.get("service.name")
            if type(value) is str:
                return value
    except Exception:
        pass
    return None


def _local_span_ids(
    backend: ObservabilityBackend,
    span: object,
) -> tuple[str, str] | None:
    """Prove that ``span`` is the exact local OTel span active on ``backend``."""

    try:
        from .otel_backend import OpenTelemetryBackend, OpenTelemetrySpan

        if type(backend) is not OpenTelemetryBackend:
            return None
        if type(span) is not OpenTelemetrySpan:
            return None
        span_context = span._span.get_span_context()
        if not span_context.is_valid:
            return None
        trace_id = f"{span_context.trace_id:032x}"
        span_id = f"{span_context.span_id:016x}"
        current = backend.current_trace_ids()
        if current.trace_id != trace_id or current.span_id != span_id:
            return None
        return trace_id, span_id
    except Exception:
        return None


def admit_current_segment(
    backend: ObservabilityBackend,
    turn_context: TurnContext | None,
    span: object,
) -> TraceOwnershipBinding | None:
    """Admit the active canonical Agent span as one trusted local segment root."""

    active, index, epoch = _runtime_state(backend)
    if not active or turn_context is None:
        return None

    try:
        from ..identity_context import TurnContext as RuntimeTurnContext

        if type(turn_context) is not RuntimeTurnContext:
            return None
        local_ids = _local_span_ids(backend, span)
        if local_ids is None:
            return None
        trace_id, root_span_id = local_ids
        service_name = _service_name(backend)
        if service_name is None:
            return None
        handle = index.admit_segment(
            trace_id=trace_id,
            root_span_id=root_span_id,
            principal_id=turn_context.principal_id,
            room_id=turn_context.room_id,
            project_id=turn_context.project_id,
            service=service_name,
            entry_point=turn_context.entry_point,
            private_session=turn_context.private_session,
            server_bound_project=turn_context.server_bound_project,
        )
    except Exception:
        return None

    if handle is None:
        return None
    return TraceOwnershipBinding(index=index, epoch=epoch, handle=handle)


def _semantic_kind(operation: object) -> str | None:
    if type(operation) is not str:
        return None
    if operation == "invoke_agent":
        return "invoke_agent"
    if operation == "chat":
        return "chat"
    if operation == "execute_tool":
        return "execute_tool"
    if operation == "provider_sdk":
        return "provider_sdk"
    return "internal"


def _poison_binding(binding: TraceOwnershipBinding, semantic_kind: str) -> None:
    """Best-effort fail-closed marker for an incomplete current generation."""

    try:
        binding.index.register_span(
            binding.handle,
            span_id=None,
            semantic_kind=semantic_kind,
        )
    except Exception:
        pass


def register_current_span(
    backend: ObservabilityBackend,
    operation: object,
    span: object,
) -> bool:
    """Register one proven local UAG-owned span from its trusted operation kind."""

    binding = _CURRENT_BINDING.get()
    if binding is None:
        return False

    semantic_kind = _semantic_kind(operation)
    if semantic_kind is None:
        _poison_binding(binding, "unknown")
        return False

    active, index, epoch = _runtime_state(backend)
    if not active or index is not binding.index or epoch != binding.epoch:
        return False

    try:
        local_ids = _local_span_ids(backend, span)
        if local_ids is None:
            _poison_binding(binding, semantic_kind)
            return False
        trace_id, span_id = local_ids
        if trace_id != binding.handle.trace_id:
            _poison_binding(binding, semantic_kind)
            return False
        registered = binding.index.register_span(
            binding.handle,
            span_id=span_id,
            semantic_kind=semantic_kind,
        )
    except Exception:
        registered = False

    if not registered:
        _poison_binding(binding, semantic_kind)
    return registered


def install_trace_ownership_span_binding() -> None:
    """Wrap UAG's OTel span factory so each local child is registered once."""

    try:
        from .otel_backend import OpenTelemetryBackend

        original = OpenTelemetryBackend.start_span
        if getattr(original, "_uag_trace_ownership_wrapped", False):
            return

        @contextmanager
        @wraps(original)
        def observed(
            self: Any,
            operation: str,
            *,
            attributes: Mapping[str, Any] | None = None,
            root: bool = False,
        ) -> Iterator[ObservabilitySpan]:
            with original(
                self,
                operation,
                attributes=attributes,
                root=root,
            ) as span:
                try:
                    register_current_span(self, operation, span)
                except Exception:
                    pass
                yield span

        observed._uag_trace_ownership_wrapped = True  # type: ignore[attr-defined]
        OpenTelemetryBackend.start_span = observed
    except Exception:
        pass


def _runtime_index_snapshot_for_tests() -> tuple[TraceOwnershipIndex, int]:
    """Expose the current process-local index epoch to isolated regression tests."""

    with _STATE_LOCK:
        return _INDEX, _EPOCH


def _reset_trace_ownership_runtime_for_tests() -> None:
    """Reset the process-local binding/index state for isolated unit tests."""

    global _INDEX, _EPOCH, _BACKEND, _SETTINGS
    with _STATE_LOCK:
        _INDEX = TraceOwnershipIndex()
        _EPOCH += 1
        _BACKEND = None
        _SETTINGS = None
    _CURRENT_BINDING.set(None)


__all__ = [
    "TraceOwnershipBinding",
    "admit_current_segment",
    "bind_current_trace_ownership",
    "bound_trace_ownership_scope",
    "install_trace_ownership_span_binding",
    "mask_current_trace_ownership",
    "masked_trace_ownership_scope",
    "register_current_span",
    "reset_current_trace_ownership",
]

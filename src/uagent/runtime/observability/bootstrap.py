"""Process-level observability backend bootstrap."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from .api import ObservabilityBackend
from .dependencies import ensure_otel_dependencies
from .noop import NOOP_BACKEND
from .settings import ObservabilitySettings

BackendFactory = Callable[[ObservabilitySettings], ObservabilityBackend]


@dataclass(frozen=True)
class ObservabilityBootstrapResult:
    settings: ObservabilitySettings
    backend: ObservabilityBackend
    dependencies_ready: bool
    reason: str


_LOCK = threading.Lock()
_RESULT: ObservabilityBootstrapResult | None = None


def _shutdown_backend(backend: ObservabilityBackend) -> None:
    shutdown = getattr(backend, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown()
        except Exception:
            pass


def initialize_observability(
    settings: ObservabilitySettings,
    *,
    backend_factory: BackendFactory | None = None,
) -> ObservabilityBootstrapResult:
    """Initialize the process-level observability projection safely.

    OTel dependencies and the concrete adapter are loaded only after product-level
    activation resolves to enabled. Any dependency/adapter failure degrades to the
    no-op backend and never changes Agent execution behavior.
    """

    global _RESULT
    with _LOCK:
        if _RESULT is not None and _RESULT.settings == settings:
            return _RESULT
        if _RESULT is not None:
            _shutdown_backend(_RESULT.backend)
            _RESULT = None

        if not settings.enabled:
            _RESULT = ObservabilityBootstrapResult(
                settings=settings,
                backend=NOOP_BACKEND,
                dependencies_ready=False,
                reason="disabled",
            )
            return _RESULT

        try:
            dependencies_ready = ensure_otel_dependencies(settings)
        except Exception:
            dependencies_ready = False
        if not dependencies_ready:
            _RESULT = ObservabilityBootstrapResult(
                settings=settings,
                backend=NOOP_BACKEND,
                dependencies_ready=False,
                reason="dependencies_unavailable",
            )
            return _RESULT

        if backend_factory is None:
            try:
                from .otel_backend import create_otel_backend

                backend_factory = create_otel_backend
            except Exception:
                backend_factory = None
        if backend_factory is None:
            _RESULT = ObservabilityBootstrapResult(
                settings=settings,
                backend=NOOP_BACKEND,
                dependencies_ready=True,
                reason="backend_unavailable",
            )
            return _RESULT

        try:
            backend = backend_factory(settings)
        except Exception:
            _RESULT = ObservabilityBootstrapResult(
                settings=settings,
                backend=NOOP_BACKEND,
                dependencies_ready=True,
                reason="backend_initialization_failed",
            )
            return _RESULT

        _RESULT = ObservabilityBootstrapResult(
            settings=settings,
            backend=backend,
            dependencies_ready=True,
            reason="enabled",
        )
        try:
            from .boundary_instrumentation import (
                install_runtime_boundary_instrumentation,
            )

            install_runtime_boundary_instrumentation()
        except Exception:
            pass
        return _RESULT


def get_observability_backend() -> ObservabilityBackend:
    """Return the active backend or the process-safe no-op backend."""

    result = _RESULT
    return result.backend if result is not None else NOOP_BACKEND


def _reset_observability_state_for_tests() -> None:
    """Reset process-level bootstrap state for isolated unit tests."""

    global _RESULT
    with _LOCK:
        if _RESULT is not None:
            _shutdown_backend(_RESULT.backend)
        _RESULT = None

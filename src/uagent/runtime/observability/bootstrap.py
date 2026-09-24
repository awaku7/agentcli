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


def initialize_observability(
    settings: ObservabilitySettings,
    *,
    backend_factory: BackendFactory | None = None,
) -> ObservabilityBootstrapResult:
    """Initialize observability once per process.

    PR1 intentionally ships only the provider-neutral/no-op foundation. The
    OpenTelemetry backend factory is supplied by the later adapter PR. Until
    then, enabled settings can validate/install dependencies without changing
    Agent execution behavior.
    """

    global _RESULT
    with _LOCK:
        if _RESULT is not None:
            return _RESULT

        if not settings.enabled:
            _RESULT = ObservabilityBootstrapResult(
                settings=settings,
                backend=NOOP_BACKEND,
                dependencies_ready=False,
                reason="disabled",
            )
            return _RESULT

        dependencies_ready = ensure_otel_dependencies(settings)
        if not dependencies_ready:
            _RESULT = ObservabilityBootstrapResult(
                settings=settings,
                backend=NOOP_BACKEND,
                dependencies_ready=False,
                reason="dependencies_unavailable",
            )
            return _RESULT

        if backend_factory is None:
            _RESULT = ObservabilityBootstrapResult(
                settings=settings,
                backend=NOOP_BACKEND,
                dependencies_ready=True,
                reason="backend_not_configured",
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
        return _RESULT


def get_observability_backend() -> ObservabilityBackend:
    """Return the active backend or the process-safe no-op backend."""

    result = _RESULT
    return result.backend if result is not None else NOOP_BACKEND


def _reset_observability_state_for_tests() -> None:
    """Reset process-level bootstrap state for isolated unit tests."""

    global _RESULT
    with _LOCK:
        _RESULT = None

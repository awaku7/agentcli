"""Lazy OpenTelemetry dependency readiness for the observability backend."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from .settings import ObservabilitySettings

OTEL_VERSION = "1.44.0"


@dataclass(frozen=True)
class OTelDependency:
    package_name: str
    module_name: str
    version_spec: str


OTEL_DEPENDENCIES = (
    OTelDependency("opentelemetry-api", "opentelemetry", f"=={OTEL_VERSION}"),
    OTelDependency("opentelemetry-sdk", "opentelemetry.sdk", f"=={OTEL_VERSION}"),
    OTelDependency(
        "opentelemetry-exporter-otlp",
        "opentelemetry.exporter.otlp",
        f"=={OTEL_VERSION}",
    ),
)

Installer = Callable[..., bool]

_LOCK = threading.Lock()
_CACHED_RESULT: bool | None = None


def ensure_otel_dependencies(
    settings: ObservabilitySettings,
    *,
    installer: Installer | None = None,
) -> bool:
    """Ensure the supported OTel package set is importable once per process.

    Nothing is installed when product-level OTel activation is disabled.
    Installation is delegated to ``_pip_auto.install_with_status`` so
    ``UAGENT_AUTO_INSTALL=allow|prompt|off`` remains authoritative.
    """

    if not settings.enabled:
        return False

    global _CACHED_RESULT
    with _LOCK:
        if _CACHED_RESULT is not None:
            return _CACHED_RESULT

        if installer is None:
            from uagent._pip_auto import install_with_status

            installer = install_with_status

        for dependency in OTEL_DEPENDENCIES:
            ok = installer(
                dependency.package_name,
                dependency.module_name,
                display_name=dependency.package_name,
                version_spec=dependency.version_spec,
            )
            if not ok:
                _CACHED_RESULT = False
                return False

        _CACHED_RESULT = True
        return True


def _reset_dependency_state_for_tests() -> None:
    """Reset process-level readiness cache for isolated unit tests."""

    global _CACHED_RESULT
    with _LOCK:
        _CACHED_RESULT = None

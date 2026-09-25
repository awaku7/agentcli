"""UAG provider-neutral observability foundation."""

from .api import ObservabilityBackend, ObservabilitySpan, TraceIds
from .bootstrap import (
    ObservabilityBootstrapResult,
    get_observability_backend,
    initialize_observability,
)
from .settings import (
    ObservabilitySettings,
    get_observability_settings,
    resolve_observability_settings,
)

__all__ = [
    "ObservabilityBackend",
    "ObservabilityBootstrapResult",
    "ObservabilitySettings",
    "ObservabilitySpan",
    "TraceIds",
    "get_observability_backend",
    "get_observability_settings",
    "initialize_observability",
    "resolve_observability_settings",
]

"""No-op observability backend used when tracing is disabled or unavailable."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from .api import ObservabilitySpan, TraceIds


class NoOpSpan:
    """Span implementation that intentionally performs no work."""

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def add_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None:
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None


class NoOpObservabilityBackend:
    """Backend that keeps runtime instrumentation safe when OTel is off."""

    @property
    def enabled(self) -> bool:
        return False

    @contextmanager
    def start_span(
        self,
        operation: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[ObservabilitySpan]:
        yield NOOP_SPAN

    def record_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None:
        return None

    def current_trace_ids(self) -> TraceIds:
        return TraceIds()


NOOP_SPAN = NoOpSpan()
NOOP_BACKEND = NoOpObservabilityBackend()

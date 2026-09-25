"""Provider-neutral observability contracts for UAG runtime code."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class TraceIds:
    """Current trace identifiers, when an observability backend provides them."""

    trace_id: str | None = None
    span_id: str | None = None


class ObservabilitySpan(Protocol):
    """Minimal span surface consumed by UAG runtime code."""

    def set_attribute(self, key: str, value: Any) -> None: ...

    def add_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None: ...

    def record_exception(self, exc: BaseException) -> None: ...


class ObservabilityBackend(Protocol):
    """Provider-neutral backend contract.

    Runtime code depends on this protocol rather than OpenTelemetry classes.
    Semantic-convention mapping stays inside the OTel adapter added later.
    """

    @property
    def enabled(self) -> bool: ...

    def start_span(
        self,
        operation: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> AbstractContextManager[ObservabilitySpan]: ...

    def record_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None: ...

    def current_trace_ids(self) -> TraceIds: ...

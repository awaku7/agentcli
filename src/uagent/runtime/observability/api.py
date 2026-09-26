"""Provider-neutral observability contracts for UAG runtime code."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Protocol


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

    def set_status(self, status: str, description: str | None = None) -> None: ...


class ObservabilityBackend(Protocol):
    """Provider-neutral backend contract.

    Runtime code depends on this protocol rather than OpenTelemetry classes.
    Semantic-convention mapping stays inside the OTel adapter.
    """

    @property
    def enabled(self) -> bool: ...

    def start_span(
        self,
        operation: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        root: bool = False,
    ) -> AbstractContextManager[ObservabilitySpan]: ...

    def record_event(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> None: ...

    def record_counter(
        self,
        name: str,
        value: int | float = 1,
        attributes: Mapping[str, Any] | None = None,
    ) -> None: ...

    def record_histogram(
        self,
        name: str,
        value: int | float,
        attributes: Mapping[str, Any] | None = None,
    ) -> None: ...

    def inject_context(self, carrier: MutableMapping[str, str]) -> None: ...

    def attach_remote_context(
        self, carrier: Mapping[str, str]
    ) -> AbstractContextManager[bool]: ...

    def current_trace_ids(self) -> TraceIds: ...

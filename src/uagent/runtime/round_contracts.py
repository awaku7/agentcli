"""Provider-neutral contracts for one LLM turn and its execution rounds.

The existing LLM loop remains the active implementation.  These types are the
stable seam used while adapters are introduced incrementally; they deliberately
avoid importing provider SDKs, core state, or host-rendering code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Literal, Mapping, Protocol, Sequence


RoundStatus = Literal[
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "interrupted",
]
StreamMode = Literal["delta", "snapshot"]


@dataclass(frozen=True)
class RoundIdentifiers:
    """Correlate one user turn, its LLM rounds, and provider I/O.

    ``turn_id`` spans a user input through the end of its tool loop.  A
    ``round_id`` identifies one LLM execution in that loop, while ``attempt_id``
    identifies one transmission attempt for that round.
    """

    turn_id: str
    round_id: str
    attempt_id: str
    request_id: str
    stream_id: str
    session_generation: int


@dataclass(frozen=True)
class ContextPlan:
    """Provider-neutral context selected for an LLM execution.

    Callers must treat ``messages`` and the other collection fields as
    immutable.  Provider-specific transforms belong in ``ProviderProjection``.
    """

    plan_id: str
    messages: tuple[Mapping[str, Any], ...]
    tool_specs: tuple[Mapping[str, Any], ...] = ()
    decisions: tuple[Mapping[str, Any], ...] = ()
    telemetry: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderProjection:
    """A provider/model-specific, but not yet serialized, request projection."""

    plan_id: str
    projection_id: str
    provider: str
    model: str
    transport: str
    messages: tuple[Mapping[str, Any], ...]
    tool_specs: tuple[Mapping[str, Any], ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SerializedRequest:
    """Wire-format request ready for a provider SDK or HTTP client."""

    identifiers: RoundIdentifiers
    plan_id: str
    projection_id: str
    provider: str
    model: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class StreamEvent:
    """Normalized provider event consumed by host renderers and collectors."""

    type: str
    identifiers: RoundIdentifiers
    sequence_number: int
    timestamp: float
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoundResult:
    """Collected terminal result for exactly one LLM round."""

    identifiers: RoundIdentifiers
    plan_id: str
    projection_id: str
    status: RoundStatus
    assistant_text: str = ""
    reasoning_text: str = ""
    partial_text: str = ""
    tool_calls: tuple[Mapping[str, Any], ...] = ()
    usage: Mapping[str, Any] = field(default_factory=dict)
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)
    continuation_update: Mapping[str, Any] = field(default_factory=dict)
    error: Mapping[str, Any] | None = None
    recovery_hint: Mapping[str, Any] | None = None


class CancellationToken(Protocol):
    """Minimal cancellation boundary shared by sync provider adapters."""

    def is_cancelled(self) -> bool: ...


class ProviderRuntime(Protocol):
    """Provider adapter contract used by the future orchestration registry."""

    def project(
        self, plan: ContextPlan, session: Mapping[str, Any]
    ) -> ProviderProjection: ...

    def serialize(self, projection: ProviderProjection) -> SerializedRequest: ...

    def run(
        self, request: SerializedRequest, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]: ...


class UnknownProviderRuntime(KeyError):
    """Raised when no adapter was registered for a requested provider key."""


class ProviderRuntimeRegistry:
    """Small registry that keeps provider dispatch out of the orchestration loop."""

    def __init__(self) -> None:
        self._runtimes: dict[str, ProviderRuntime] = {}

    @staticmethod
    def _key(provider: str) -> str:
        return (provider or "").strip().lower()

    def register(self, provider: str, runtime: ProviderRuntime) -> None:
        key = self._key(provider)
        if not key:
            raise ValueError("provider key must not be empty")
        if key in self._runtimes:
            raise ValueError(f"provider runtime already registered: {key}")
        self._runtimes[key] = runtime

    def resolve(self, provider: str) -> ProviderRuntime:
        key = self._key(provider)
        try:
            return self._runtimes[key]
        except KeyError as exc:
            raise UnknownProviderRuntime(key or "<empty>") from exc

    def providers(self) -> Sequence[str]:
        return tuple(sorted(self._runtimes))


def validate_stream_events(events: Iterable[StreamEvent]) -> None:
    """Validate one complete normalized stream without exposing validator state."""

    # Delayed import avoids a module cycle: round_runtime uses StreamEvent.
    from .round_runtime import StreamEventValidator

    validator = StreamEventValidator()
    for event in events:
        validator.accept(event)
    validator.require_terminal()


__all__ = [
    "CancellationToken",
    "ContextPlan",
    "ProviderProjection",
    "ProviderRuntime",
    "ProviderRuntimeRegistry",
    "RoundIdentifiers",
    "RoundResult",
    "RoundStatus",
    "SerializedRequest",
    "StreamEvent",
    "StreamMode",
    "UnknownProviderRuntime",
    "validate_stream_events",
]

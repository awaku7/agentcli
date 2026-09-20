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
    "continue",
    "failed",
    "cancelled",
    "timed_out",
    "interrupted",
]
StreamMode = Literal["delta", "snapshot"]
TransportKind = Literal["chat_completions", "responses"]


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
class RoundTransportSelection:
    """Resolved transport choice shared by registry and legacy bridges."""

    transport: TransportKind
    streaming: bool

    @classmethod
    def from_flags(
        cls, *, use_responses_api: bool, stream_responses: bool
    ) -> "RoundTransportSelection":
        return cls(
            transport="responses" if use_responses_api else "chat_completions",
            streaming=bool(stream_responses),
        )

    @property
    def use_responses_api(self) -> bool:
        """Compatibility Boolean for code not yet migrated to ``transport``."""
        return self.transport == "responses"


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
    input_fingerprint: str = ""
    history_revision: str = ""
    schema_revision: str = "1"


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
class RoundSummary:
    """Bounded, provider-neutral telemetry for one completed round.

    The summary is deliberately numeric/enum-like. Provider payloads,
    prompts, tool arguments, and tool results do not belong in this object;
    those remain subject to the normal masking and persistence policies.
    """

    status: RoundStatus
    duration_ms: int | float = 0
    event_count: int = 0
    tool_call_count: int = 0
    assistant_chars: int = 0
    reasoning_chars: int = 0
    request_tokens: int = 0
    projection_size: int = 0
    tool_schema_size: int = 0
    recovery_strategy: str = ""
    fallback_count: int = 0
    duplicate_event_count: int = 0
    out_of_order_event_count: int = 0
    usage_delta: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable telemetry projection."""

        return {
            "status": self.status,
            "duration_ms": self.duration_ms,
            "event_count": self.event_count,
            "tool_call_count": self.tool_call_count,
            "assistant_chars": self.assistant_chars,
            "reasoning_chars": self.reasoning_chars,
            "request_tokens": self.request_tokens,
            "projection_size": self.projection_size,
            "tool_schema_size": self.tool_schema_size,
            "recovery_strategy": self.recovery_strategy,
            "fallback_count": self.fallback_count,
            "duplicate_event_count": self.duplicate_event_count,
            "out_of_order_event_count": self.out_of_order_event_count,
            "usage_delta": dict(self.usage_delta),
        }


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
    summary: RoundSummary | None = None


class CancellationToken(Protocol):
    """Minimal cancellation boundary shared by sync provider adapters."""

    def is_cancelled(self) -> bool: ...


class ProviderRuntime(Protocol):
    """Provider adapter contract used by the future orchestration registry."""

    capabilities: Any

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

    def capability_snapshot(self, provider: str) -> Any:
        """Return the registered runtime's resolved capability snapshot."""
        runtime = self.resolve(provider)
        return getattr(runtime, "capabilities", None)

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
    "RoundSummary",
    "RoundTransportSelection",
    "SerializedRequest",
    "StreamEvent",
    "StreamMode",
    "TransportKind",
    "UnknownProviderRuntime",
    "validate_stream_events",
]

"""Host-neutral rendering and collection for normalized stream events.

Provider adapters emit :class:`StreamEvent` values.  This module consumes those
values without knowing about CLI, GUI, Web, provider SDKs, or ``core``. Hosts
can use ``CallbackStreamRenderer`` while the round orchestrator uses
``CollectingStreamRenderer`` to build the final result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .round_contracts import StreamEvent


@dataclass(frozen=True)
class StreamCallbacks:
    """Optional host callbacks for a normalized stream renderer."""

    on_delta: Callable[[str], None] | None = None
    on_snapshot: Callable[[str], None] | None = None
    on_reasoning: Callable[[str], None] | None = None
    on_tool_call: Callable[[Mapping[str, Any]], None] | None = None
    on_terminal: Callable[[str, Mapping[str, Any]], None] | None = None


@dataclass(frozen=True)
class RenderedStream:
    """Collected display text and tool calls for one normalized stream."""

    assistant_text: str = ""
    partial_text: str = ""
    reasoning_text: str = ""
    tool_calls: tuple[Mapping[str, Any], ...] = ()
    terminal_type: str = ""
    terminal_data: Mapping[str, Any] = field(default_factory=dict)


class StreamRenderer:
    """Minimal host-renderer protocol."""

    def on_event(self, event: StreamEvent) -> None:
        raise NotImplementedError

    def result(self) -> RenderedStream:
        raise NotImplementedError


class CollectingStreamRenderer(StreamRenderer):
    """Collect events without performing any user-interface side effects."""

    def __init__(self) -> None:
        self._delta_parts: list[str] = []
        self._snapshot = ""
        self._reasoning_parts: list[str] = []
        self._tool_calls: list[Mapping[str, Any]] = []
        self._terminal_type = ""
        self._terminal_data: Mapping[str, Any] = {}

    def on_event(self, event: StreamEvent) -> None:
        if event.type == "TextDelta":
            self._delta_parts.append(str(event.data.get("text") or ""))
        elif event.type == "TextSnapshot":
            self._snapshot = str(event.data.get("text") or "")
        elif event.type == "ReasoningDelta":
            self._reasoning_parts.append(str(event.data.get("text") or ""))
        elif event.type == "ToolCallCompleted":
            self._tool_calls.append(dict(event.data))
        elif event.type in {
            "ResponseCompleted",
            "ResponseFailed",
            "ResponseCancelled",
            "ResponseTimedOut",
            "ResponseInterrupted",
        }:
            self._terminal_type = event.type
            self._terminal_data = dict(event.data)

    def result(self) -> RenderedStream:
        partial = "".join(self._delta_parts)
        return RenderedStream(
            assistant_text=self._snapshot or partial,
            partial_text=partial,
            reasoning_text="".join(self._reasoning_parts),
            tool_calls=tuple(self._tool_calls),
            terminal_type=self._terminal_type,
            terminal_data=self._terminal_data,
        )


class CallbackStreamRenderer(StreamRenderer):
    """Forward normalized events to host-owned callbacks.

    Callbacks are optional and receive only provider-neutral data.  In
    particular, this class does not inspect terminal capabilities or mutate a
    CLI/GUI/Web object.
    """

    def __init__(
        self,
        *,
        callbacks: StreamCallbacks | None = None,
        on_delta: Callable[[str], None] | None = None,
        on_snapshot: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
        on_tool_call: Callable[[Mapping[str, Any]], None] | None = None,
        on_terminal: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> None:
        callbacks = callbacks or StreamCallbacks()
        self._collector = CollectingStreamRenderer()
        self._on_delta = on_delta or callbacks.on_delta
        self._on_snapshot = on_snapshot or callbacks.on_snapshot
        self._on_reasoning = on_reasoning or callbacks.on_reasoning
        self._on_tool_call = on_tool_call or callbacks.on_tool_call
        self._on_terminal = on_terminal or callbacks.on_terminal
        self._last_terminal = ""

    def on_event(self, event: StreamEvent) -> None:
        self._collector.on_event(event)
        if event.type == "TextDelta" and self._on_delta is not None:
            self._on_delta(str(event.data.get("text") or ""))
        elif event.type == "TextSnapshot" and self._on_snapshot is not None:
            self._on_snapshot(str(event.data.get("text") or ""))
        elif event.type == "ReasoningDelta" and self._on_reasoning is not None:
            self._on_reasoning(str(event.data.get("text") or ""))
        elif event.type == "ToolCallCompleted" and self._on_tool_call is not None:
            self._on_tool_call(dict(event.data))
        elif event.type.startswith("Response") and event.type != "ResponseStarted":
            if event.type != self._last_terminal and self._on_terminal is not None:
                self._on_terminal(event.type, dict(event.data))
            self._last_terminal = event.type

    def result(self) -> RenderedStream:
        return self._collector.result()


def collect_stream_events(
    events: list[StreamEvent] | tuple[StreamEvent, ...],
    *,
    renderer: StreamRenderer | None = None,
) -> RenderedStream:
    """Collect events through a renderer and return the normalized result."""

    target = renderer or CollectingStreamRenderer()
    for event in events:
        target.on_event(event)
    return target.result()


__all__ = [
    "CallbackStreamRenderer",
    "CollectingStreamRenderer",
    "RenderedStream",
    "StreamCallbacks",
    "StreamRenderer",
    "collect_stream_events",
]

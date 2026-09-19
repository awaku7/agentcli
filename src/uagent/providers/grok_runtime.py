"""Registry adapter for Grok's xAI SDK/gRPC transport.

The registry owns the round boundary, while xAI message/tool conversion and
stream parsing remain provider-specific. No host object or callback is passed
into this adapter; parser callbacks only collect normalized data locally.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from ..runtime.round_contracts import CancellationToken, SerializedRequest, StreamEvent
from ..runtime.stream_renderer import StreamCallbacks
from .llm_grok import (
    build_xai_messages,
    build_xai_tools,
    parse_xai_response,
    parse_xai_stream,
)
from .openai_compatible_runtime import OpenAICompatibleRuntime


class GrokGrpcProviderRuntime(OpenAICompatibleRuntime):
    """Adapt xAI SDK/gRPC responses to the provider-neutral event contract."""

    def run(
        self, request: SerializedRequest, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        self._sequence = 0
        payload = request.payload
        call_messages = list(payload.get("messages") or ())
        instructions, xai_messages = build_xai_messages(call_messages)
        request_tools = build_xai_tools(
            bool(payload.get("tools")), call_messages=call_messages
        )
        options = {
            key: value
            for key, value in payload.items()
            if key not in {"model", "messages", "tools", "instructions"}
        }
        if instructions:
            options["instructions"] = instructions
        if request_tools:
            options["tools"] = request_tools
            options.setdefault("tool_choice", "auto")

        yield self._event("ResponseStarted", {"stream_mode": "delta"})
        try:
            if cancellation.is_cancelled():
                yield self._event("ResponseCancelled", {"reason": "cancelled"})
                return
            chat = self._client.chat.create(
                model=request.model,
                messages=xai_messages,
                **options,
            )
            if self._streaming:
                deltas: list[str] = []
                reasoning: list[str] = []
                tool_calls: list[Mapping[str, Any]] = []
                parse_xai_stream(
                    chat.stream(),
                    callbacks=StreamCallbacks(
                        on_delta=deltas.append,
                        on_reasoning=reasoning.append,
                        on_tool_call=tool_calls.append,
                    ),
                )
                for text in reasoning:
                    yield self._event("ReasoningDelta", {"text": text})
                for text in deltas:
                    if cancellation.is_cancelled():
                        yield self._event("ResponseCancelled", {"reason": "cancelled"})
                        return
                    if text != "\n":
                        yield self._event("TextDelta", {"text": text})
                normalized, tool_events = self._normalize_tool_calls(tool_calls)
                yield from tool_events
                yield from self._complete_tools(normalized)
            else:
                text, tool_calls = parse_xai_response(chat.sample())
                if text:
                    yield self._event("TextDelta", {"text": text})
                normalized, tool_events = self._normalize_tool_calls(tool_calls)
                yield from tool_events
                yield from self._complete_tools(normalized)
            yield self._event("ResponseCompleted", {})
        except Exception as exc:
            yield self._event(
                "ResponseFailed",
                {"message": str(exc), "error_type": type(exc).__name__},
            )

    def _normalize_tool_calls(
        self, tool_calls: list[Mapping[str, Any]]
    ) -> tuple[dict[int, dict[str, str]], list[StreamEvent]]:
        normalized: dict[int, dict[str, str]] = {}
        events: list[StreamEvent] = []
        for index, call in enumerate(tool_calls):
            function = call.get("function") or {}
            name = str(function.get("name") or "")
            arguments = str(function.get("arguments") or "")
            call_id = str(call.get("id") or index)
            normalized[index] = {"id": call_id, "name": name, "arguments": arguments}
            events.append(
                self._event(
                    "ToolCallDelta",
                    {
                        "index": index,
                        "tool_call_id": call_id,
                        "name_fragment": name,
                        "arguments_fragment": arguments,
                    },
                )
            )
        return normalized, events

    def _event(self, event_type: str, data: Mapping[str, Any]) -> StreamEvent:
        return super()._event(event_type, data)


__all__ = ["GrokGrpcProviderRuntime"]

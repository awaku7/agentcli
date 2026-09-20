"""Registry adapter for Grok's xAI SDK/gRPC transport.

The registry owns the round boundary, while xAI message/tool conversion and
stream parsing remain provider-specific. Provider chunks are converted to
normalized events as they arrive, without buffering a complete response.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from ..runtime.round_contracts import CancellationToken, SerializedRequest, StreamEvent
from .llm_grok import (
    build_xai_messages,
    build_xai_tools,
    iter_xai_stream_parts,
    parse_xai_response,
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
                tool_index = 0
                parts = iter(iter_xai_stream_parts(chat.stream()))
                while True:
                    if cancellation.is_cancelled():
                        yield self._event("ResponseCancelled", {"reason": "cancelled"})
                        return
                    try:
                        part_type, value = next(parts)
                    except StopIteration:
                        break
                    if cancellation.is_cancelled():
                        yield self._event("ResponseCancelled", {"reason": "cancelled"})
                        return
                    if part_type == "text":
                        yield self._event("TextDelta", {"text": str(value)})
                    elif part_type == "reasoning":
                        yield self._event("ReasoningDelta", {"text": str(value)})
                    elif part_type == "tool_call":
                        normalized, tool_events = self._normalize_tool_calls(
                            [value], start_index=tool_index
                        )
                        yield from tool_events
                        yield from self._complete_tools(normalized)
                        tool_index += 1
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
        self,
        tool_calls: list[Mapping[str, Any]],
        *,
        start_index: int = 0,
    ) -> tuple[dict[int, dict[str, str]], list[StreamEvent]]:
        normalized: dict[int, dict[str, str]] = {}
        events: list[StreamEvent] = []
        for index, call in enumerate(tool_calls, start=start_index):
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

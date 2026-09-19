"""Registry adapter for PFN/PLaMo's OpenAI-compatible endpoint.

PFN uses the standard Chat Completions transport but has a provider-specific
streaming/tool contract. Projection and serialization are inherited from the
OpenAI-compatible runtime; only the wire event parser is specialized here.
The legacy ``pfn_chat_with_tools`` entry point remains available while this
adapter is adopted behind the registry feature gate.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterator, Mapping

from ..runtime.round_contracts import (
    CancellationToken,
    ContextPlan,
    ProviderProjection,
    SerializedRequest,
    StreamEvent,
)
from .llm_pfn import (
    _pfn_messages,
    iter_pfn_stream_content,
    parse_pfn_response,
)
from .openai_compatible_runtime import OpenAICompatibleRuntime


class PfnProviderRuntime(OpenAICompatibleRuntime):
    """Adapt PFN's special tool and stream behavior to normalized events."""

    def project(
        self, plan: ContextPlan, session: Mapping[str, Any]
    ) -> ProviderProjection:
        if plan.tool_specs:
            plan = replace(
                plan,
                messages=tuple(
                    _pfn_messages(
                        [dict(message) for message in plan.messages],
                        send_tools_this_round=True,
                    )
                ),
            )
        return super().project(plan, session)

    def run(
        self, request: SerializedRequest, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        self._sequence = 0
        payload = {
            key: value for key, value in request.payload.items() if key != "transport"
        }
        request_tools = request.payload.get("tools") or ()
        use_stream = bool(self._streaming and not request_tools)
        yield self._event("ResponseStarted", {"stream_mode": "delta"})
        try:
            if cancellation.is_cancelled():
                yield self._event("ResponseCancelled", {"reason": "cancelled"})
                return
            response = self._client.chat.completions.create(
                **payload,
                stream=use_stream,
            )
            if use_stream:
                for text in iter_pfn_stream_content(response):
                    if cancellation.is_cancelled():
                        yield self._event("ResponseCancelled", {"reason": "cancelled"})
                        return
                    yield self._event("TextDelta", {"text": text})
            else:
                text, calls = parse_pfn_response(response)
                if text:
                    yield self._event("TextDelta", {"text": text})
                normalized = {
                    index: {
                        "id": call.get("id", ""),
                        "name": call.get("function", {}).get("name", ""),
                        "arguments": call.get("function", {}).get("arguments", ""),
                    }
                    for index, call in enumerate(calls)
                }
                for index, call in normalized.items():
                    yield self._event(
                        "ToolCallDelta",
                        {
                            "index": index,
                            "tool_call_id": str(call["id"] or index),
                            "name_fragment": call["name"],
                            "arguments_fragment": call["arguments"],
                        },
                    )
                yield from self._complete_tools(normalized)
            yield self._event("ResponseCompleted", {})
        except Exception as exc:
            yield self._event(
                "ResponseFailed",
                {"message": str(exc), "error_type": type(exc).__name__},
            )


__all__ = ["PfnProviderRuntime"]

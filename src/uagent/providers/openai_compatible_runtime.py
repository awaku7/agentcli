"""Provider-neutral OpenAI/Azure-compatible round adapters.

This is the first non-Inception registry adapter. It deliberately owns only
SDK calls and wire/event conversion; routing policy and host rendering remain
outside this module.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Iterator, Mapping

from ..env_utils import env_get

from ..runtime.provider_context import project_messages_for_provider
from ..runtime.round_contracts import (
    CancellationToken,
    ContextPlan,
    ProviderProjection,
    RoundIdentifiers,
    SerializedRequest,
    StreamEvent,
)
from ..runtime.round_identity import canonical_json


def _debug_enabled() -> bool:
    value = (env_get("UAGENT_DEBUG_OPENAI_RUNTIME", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _debug_runtime(event: str, **fields: Any) -> None:
    """Emit opt-in, metadata-only diagnostics for provider stream debugging."""
    if not _debug_enabled():
        return
    rendered = " ".join(f"{key}={value!r}" for key, value in fields.items())
    print(f"[OPENAI_RUNTIME] {event} {rendered}".rstrip(), file=sys.stderr)


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _extract_response_text(response: Any) -> str:
    """Recover final text when a provider omits output-text delta events."""
    direct = _mapping_value(response, "output_text")
    if isinstance(direct, str) and direct:
        return direct
    output = _mapping_value(response, "output") or ()
    parts: list[str] = []
    for item in output:
        if _mapping_value(item, "type") != "message":
            continue
        for content in _mapping_value(item, "content") or ():
            if _mapping_value(content, "type") != "output_text":
                continue
            text = _mapping_value(content, "text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "".join(parts)


class OpenAICompatibleRuntime:
    """Adapt Chat Completions or Responses requests for registry execution."""

    def __init__(
        self,
        *,
        client: Any,
        provider: str,
        model: str,
        identifiers: RoundIdentifiers,
        transport: str = "chat_completions",
        streaming: bool = True,
        options: Mapping[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._provider = (provider or "").strip().lower()
        self._model = model
        self._identifiers = identifiers
        self._transport = transport
        self._streaming = streaming
        self._options = dict(options or {})

    def project(
        self, plan: ContextPlan, session: Mapping[str, Any]
    ) -> ProviderProjection:
        messages = project_messages_for_provider(
            [dict(message) for message in plan.messages],
            provider=self._provider,
            model=self._model,
        )
        identity_factory = session.get("identity_factory")
        make_projection_id = getattr(identity_factory, "projection_id", None)
        if not callable(make_projection_id):
            raise ValueError("session must provide an identity_factory")
        projection_id = make_projection_id(
            canonical_json(
                {
                    "plan_id": plan.plan_id,
                    "provider": self._provider,
                    "model": self._model,
                    "transport": self._transport,
                    "messages": messages,
                    "options": self._options,
                }
            )
        )
        return ProviderProjection(
            plan_id=plan.plan_id,
            projection_id=projection_id,
            provider=self._provider,
            model=self._model,
            transport=self._transport,
            messages=tuple(messages),
            tool_specs=plan.tool_specs,
            options=dict(self._options),
        )

    def serialize(self, projection: ProviderProjection) -> SerializedRequest:
        input_key = "input" if projection.transport == "responses" else "messages"
        payload = {
            "model": projection.model,
            input_key: list(projection.messages),
            **projection.options,
        }
        if projection.tool_specs:
            payload.setdefault("tools", list(projection.tool_specs))
        return SerializedRequest(
            identifiers=self._identifiers,
            plan_id=projection.plan_id,
            projection_id=projection.projection_id,
            provider=projection.provider,
            model=projection.model,
            payload=payload,
        )

    def run(
        self, request: SerializedRequest, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        _debug_runtime(
            "request",
            provider=self._provider,
            transport=self._transport,
            streaming=self._streaming,
            message_count=len(
                request.payload.get("messages", request.payload.get("input", ())) or ()
            ),
            has_tools=bool(request.payload.get("tools")),
            option_keys=sorted(
                key
                for key in request.payload
                if key not in {"model", "input", "messages", "tools"}
            ),
        )
        yield self._event("ResponseStarted", {"stream_mode": "delta"})
        stream: Any = None
        try:
            if (
                request.payload.get("transport") == "responses"
                or self._transport == "responses"
            ):
                stream = self._client.responses.create(
                    **{
                        key: value
                        for key, value in request.payload.items()
                        if key != "transport"
                    },
                    stream=self._streaming,
                )
                if self._streaming:
                    yield from self._responses_events(stream, cancellation)
                else:
                    yield from self._responses_response_events(stream, cancellation)
            else:
                stream = self._client.chat.completions.create(
                    **{
                        key: value
                        for key, value in request.payload.items()
                        if key != "transport"
                    },
                    stream=self._streaming,
                )
                if self._streaming:
                    yield from self._chat_events(stream, cancellation)
                else:
                    yield from self._chat_response_events(stream, cancellation)
        except TimeoutError:
            yield self._event("ResponseTimedOut", {"reason": "timeout"})
        except Exception as exc:
            body = getattr(exc, "body", None)
            error_body = body.get("error") if isinstance(body, Mapping) else None
            if not isinstance(error_body, Mapping) and isinstance(body, Mapping):
                error_body = body
            error_message = _mapping_value(error_body, "message")
            if isinstance(error_message, str):
                error_message = " ".join(error_message.split())[:300]
            _debug_runtime(
                "error",
                error_class=type(exc).__name__,
                status_code=getattr(exc, "status_code", None),
                error_type=_mapping_value(error_body, "type"),
                error_code=_mapping_value(error_body, "code"),
                error_param=_mapping_value(error_body, "param"),
                error_message=error_message,
                body_keys=sorted(body) if isinstance(body, Mapping) else (),
            )
            yield self._event(
                "ResponseFailed",
                {"error_type": type(exc).__name__, "message": str(exc)},
            )
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()

    def _chat_response_events(
        self, response: Any, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        if cancellation.is_cancelled():
            yield self._event("ResponseCancelled", {"reason": "cancelled"})
            return
        choices = getattr(response, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        content = getattr(message, "content", None) if message is not None else None
        if isinstance(content, str) and content:
            yield self._event("TextDelta", {"text": content})
        tool_calls: dict[int, dict[str, str]] = {}
        for index, item in enumerate(getattr(message, "tool_calls", None) or []):
            function = getattr(item, "function", None)
            call_id = str(getattr(item, "id", "") or f"openai-tool-{index}")
            name = str(getattr(function, "name", "") or "")
            arguments = str(getattr(function, "arguments", "") or "")
            tool_calls[index] = {"id": call_id, "name": name, "arguments": arguments}
            yield self._event(
                "ToolCallDelta",
                {
                    "index": index,
                    "tool_call_id": call_id,
                    "name_fragment": name,
                    "arguments_fragment": arguments,
                },
            )
        yield from self._complete_tools(tool_calls)
        yield self._event("ResponseCompleted", {})

    def _responses_response_events(
        self, response: Any, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        if cancellation.is_cancelled():
            yield self._event("ResponseCancelled", {"reason": "cancelled"})
            return
        text = getattr(response, "output_text", None)
        if isinstance(text, str) and text:
            yield self._event("TextDelta", {"text": text})
        tool_calls: dict[str, dict[str, str]] = {}
        for index, item in enumerate(getattr(response, "output", None) or []):
            if str(getattr(item, "type", "") or "") != "function_call":
                continue
            call_id = str(getattr(item, "call_id", "") or getattr(item, "id", "") or "")
            if not call_id:
                continue
            name = str(getattr(item, "name", "") or "")
            arguments = getattr(item, "arguments", "")
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments, ensure_ascii=False)
            arguments = str(arguments or "")
            tool_calls[call_id] = {
                "id": call_id,
                "name": name,
                "arguments": arguments,
            }
            yield self._event(
                "ToolCallDelta",
                {
                    "index": index,
                    "tool_call_id": call_id,
                    "name_fragment": name,
                    "arguments_fragment": arguments,
                },
            )
        yield from self._complete_tools(tool_calls)
        response_id = getattr(response, "id", None)
        data = {"response_id": str(response_id)} if response_id else {}
        yield self._event("ResponseCompleted", data)

    def _event(self, event_type: str, data: Mapping[str, Any]) -> StreamEvent:
        sequence = getattr(self, "_sequence", 0)
        self._sequence = sequence + 1
        return StreamEvent(
            type=event_type,
            identifiers=self._identifiers,
            sequence_number=sequence,
            timestamp=time.time(),
            data=dict(data),
        )

    def _chat_events(
        self, stream: Any, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        tool_calls: dict[int, dict[str, str]] = {}
        if cancellation.is_cancelled():
            yield self._event("ResponseCancelled", {"reason": "cancelled"})
            return
        for chunk in stream:
            if cancellation.is_cancelled():
                yield self._event("ResponseCancelled", {"reason": "cancelled"})
                return
            choices = getattr(chunk, "choices", None) or []
            delta = getattr(choices[0], "delta", None) if choices else None
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if isinstance(content, str) and content:
                yield self._event("TextDelta", {"text": content})
            for item in getattr(delta, "tool_calls", None) or []:
                index = int(getattr(item, "index", 0) or 0)
                call = tool_calls.setdefault(
                    index, {"id": "", "name": "", "arguments": ""}
                )
                item_id = getattr(item, "id", None)
                if isinstance(item_id, str) and item_id and not call["id"]:
                    call["id"] = item_id
                call["id"] = call["id"] or f"openai-tool-{index}"
                function = getattr(item, "function", None)
                name = getattr(function, "name", "") if function else ""
                arguments = getattr(function, "arguments", "") if function else ""
                name = name if isinstance(name, str) else ""
                arguments = arguments if isinstance(arguments, str) else ""
                call["name"] += name
                call["arguments"] += arguments
                yield self._event(
                    "ToolCallDelta",
                    {
                        "index": index,
                        "tool_call_id": call["id"],
                        "name_fragment": name,
                        "arguments_fragment": arguments,
                    },
                )
        yield from self._complete_tools(tool_calls)
        yield self._event("ResponseCompleted", {})

    def _responses_events(
        self, stream: Any, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        tool_calls: dict[str, dict[str, str]] = {}
        item_to_call: dict[str, str] = {}
        pending_tool_deltas: dict[str, list[str]] = {}
        text_delta_seen = False

        def ensure_call(call_id: str) -> dict[str, str]:
            return tool_calls.setdefault(
                call_id, {"id": call_id, "name": "", "arguments": ""}
            )

        def bind_item(item_id: str, call_id: str) -> dict[str, str]:
            """Associate SDK output-item IDs with stable function call IDs."""
            item_to_call[item_id] = call_id
            call = ensure_call(call_id)
            provisional = tool_calls.pop(item_id, None)
            if provisional is not None and provisional is not call:
                if not call["name"]:
                    call["name"] = provisional["name"]
                if provisional["arguments"]:
                    call["arguments"] += provisional["arguments"]
            return call

        def record_function_item(
            item: Any, *, final: bool
        ) -> tuple[str, list[str]] | None:
            if str(getattr(item, "type", "") or "") != "function_call":
                return None
            item_id = str(getattr(item, "id", "") or "")
            call_id = str(getattr(item, "call_id", "") or item_id)
            if not call_id:
                return None
            call = bind_item(item_id, call_id) if item_id else ensure_call(call_id)
            name = str(getattr(item, "name", "") or "")
            if name:
                call["name"] = name
            arguments = getattr(item, "arguments", None)
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments, ensure_ascii=False)
            if isinstance(arguments, str) and arguments:
                if final:
                    call["arguments"] = arguments
                elif not call["arguments"]:
                    call["arguments"] = arguments
            return call_id, pending_tool_deltas.pop(item_id, [])

        if cancellation.is_cancelled():
            yield self._event("ResponseCancelled", {"reason": "cancelled"})
            return
        events = stream.iter_events() if hasattr(stream, "iter_events") else stream
        for event in events:
            if cancellation.is_cancelled():
                yield self._event("ResponseCancelled", {"reason": "cancelled"})
                return
            event_type = str(getattr(event, "type", "") or "")
            _debug_runtime(
                "event",
                event_type=event_type,
                has_response=getattr(event, "response", None) is not None,
                delta_len=len(str(getattr(event, "delta", "") or "")),
                item_type=str(
                    _mapping_value(getattr(event, "item", None), "type") or ""
                ),
            )
            if event_type == "response.output_text.delta":
                delta = str(getattr(event, "delta", "") or "")
                if delta:
                    text_delta_seen = True
                    yield self._event("TextDelta", {"text": delta})
            elif event_type == "response.output_text.done":
                if not text_delta_seen:
                    text = str(getattr(event, "text", "") or "")
                    if text:
                        text_delta_seen = True
                        yield self._event("TextDelta", {"text": text})
            elif event_type in {
                "response.reasoning_summary_text.delta",
                "response.reasoning_text.delta",
            }:
                yield self._event(
                    "ReasoningDelta", {"text": str(getattr(event, "delta", "") or "")}
                )
            elif event_type == "response.function_call_arguments.delta":
                event_id = str(
                    getattr(event, "item_id", "") or getattr(event, "call_id", "") or ""
                )
                if not event_id:
                    continue
                fragment = str(getattr(event, "delta", "") or "")
                if event_id not in item_to_call:
                    ensure_call(event_id)["arguments"] += fragment
                    pending_tool_deltas.setdefault(event_id, []).append(fragment)
                    continue
                call_id = item_to_call[event_id]
                call = ensure_call(call_id)
                call["arguments"] += fragment
                yield self._event(
                    "ToolCallDelta",
                    {
                        "tool_call_id": call_id,
                        "arguments_fragment": fragment,
                        "name_fragment": "",
                    },
                )
            elif event_type == "response.output_item.added":
                bound = record_function_item(getattr(event, "item", None), final=False)
                if bound is not None:
                    call_id, pending = bound
                    for fragment in pending:
                        yield self._event(
                            "ToolCallDelta",
                            {
                                "tool_call_id": call_id,
                                "arguments_fragment": fragment,
                                "name_fragment": "",
                            },
                        )
            elif event_type == "response.output_item.done":
                bound = record_function_item(getattr(event, "item", None), final=True)
                if bound is not None:
                    call_id, pending = bound
                    for fragment in pending:
                        yield self._event(
                            "ToolCallDelta",
                            {
                                "tool_call_id": call_id,
                                "arguments_fragment": fragment,
                                "name_fragment": "",
                            },
                        )
            elif event_type == "response.function_call_arguments.done":
                event_id = str(
                    getattr(event, "item_id", "") or getattr(event, "call_id", "") or ""
                )
                call_id = item_to_call.get(event_id, event_id)
                arguments = getattr(event, "arguments", None)
                if call_id and isinstance(arguments, str):
                    ensure_call(call_id)["arguments"] = arguments
            elif event_type == "response.completed":
                response = getattr(event, "response", None)
                fallback_text = ""
                if not text_delta_seen and response is not None:
                    fallback_text = _extract_response_text(response)
                    if fallback_text:
                        text_delta_seen = True
                        yield self._event("TextDelta", {"text": fallback_text})
                _debug_runtime(
                    "completed",
                    fallback_text_len=len(fallback_text),
                    output_count=(
                        len(_mapping_value(response, "output") or ())
                        if response is not None
                        else 0
                    ),
                    has_output_text=(
                        bool(_mapping_value(response, "output_text"))
                        if response is not None
                        else False
                    ),
                )
                yield from self._complete_tools(tool_calls)
                response_id = getattr(response, "id", None) if response else None
                data = {"response_id": str(response_id)} if response_id else {}
                yield self._event("ResponseCompleted", data)
                return
            elif event_type == "response.failed":
                yield self._event(
                    "ResponseFailed",
                    {"message": str(getattr(event, "error", "") or "")},
                )
                return
        yield from self._complete_tools(tool_calls)
        yield self._event("ResponseCompleted", {})

    def _complete_tools(
        self, tool_calls: Mapping[Any, Mapping[str, str]]
    ) -> Iterator[StreamEvent]:
        for index, call in sorted(tool_calls.items(), key=lambda item: str(item[0])):
            name = str(call.get("name") or "")
            arguments = str(call.get("arguments") or "")
            if not name:
                continue
            try:
                validated = json.loads(arguments) if arguments else {}
            except (TypeError, ValueError):
                validated = None
            if validated is None:
                continue
            yield self._event(
                "ToolCallCompleted",
                {
                    "index": index,
                    "tool_call_id": str(call.get("id") or index),
                    "name": name,
                    "arguments": arguments,
                    "validated_arguments": validated,
                },
            )


__all__ = ["OpenAICompatibleRuntime"]

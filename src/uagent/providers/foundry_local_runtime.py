"""Foundry Local runtime extensions for OpenAI-compatible chat responses.

Foundry Local models may expose reasoning through ``reasoning_content`` /
``reasoning`` fields or through ``<think>...</think>`` blocks in normal chat
content.  The generic OpenAI-compatible runtime currently normalizes only
visible chat text and tool calls, so keep the provider-specific compatibility
here and emit the common ``ReasoningDelta`` contract.
"""

from __future__ import annotations

import json
from typing import Any, Iterator, Mapping

from ..runtime.round_contracts import CancellationToken, StreamEvent
from .openai_compatible_runtime import OpenAICompatibleRuntime


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _reasoning_text(value: Any) -> str:
    """Return reasoning text from an SDK object or mapping when available."""

    for key in ("reasoning_content", "reasoning"):
        candidate = _mapping_value(value, key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def _partial_marker_suffix_length(text: str, marker: str) -> int:
    for size in range(min(len(text), len(marker) - 1), 0, -1):
        if text.endswith(marker[:size]):
            return size
    return 0


class FoundryLocalRuntime(OpenAICompatibleRuntime):
    """OpenAI-compatible runtime with Foundry Local reasoning normalization."""

    _THINK_START = "<think>"
    _THINK_END = "</think>"

    def _chat_response_events(
        self, response: Any, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        if cancellation.is_cancelled():
            yield self._event("ResponseCancelled", {"reason": "cancelled"})
            return

        choices = getattr(response, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        if message is None:
            yield self._event("ResponseCompleted", {})
            return

        explicit_reasoning = _reasoning_text(message)
        if explicit_reasoning:
            yield self._event("ReasoningDelta", {"text": explicit_reasoning})

        content = _mapping_value(message, "content")
        if isinstance(content, str) and content:
            reasoning, visible = self._split_think_text(content)
            if reasoning:
                yield self._event("ReasoningDelta", {"text": reasoning})
            if visible:
                yield self._event("TextDelta", {"text": visible})

        tool_calls: dict[int, dict[str, str]] = {}
        for index, item in enumerate(_mapping_value(message, "tool_calls") or []):
            function = _mapping_value(item, "function")
            call_id = str(_mapping_value(item, "id") or f"openai-tool-{index}")
            name = str(_mapping_value(function, "name") or "")
            arguments = _mapping_value(function, "arguments")
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments, ensure_ascii=False)
            arguments = str(arguments or "")
            tool_calls[index] = {
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
        yield self._event("ResponseCompleted", {})

    def _chat_events(
        self, stream: Any, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        tool_calls: dict[int, dict[str, str]] = {}
        in_reasoning = False
        marker_tail = ""

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

            explicit_reasoning = _reasoning_text(delta)
            if explicit_reasoning:
                yield self._event("ReasoningDelta", {"text": explicit_reasoning})

            content = _mapping_value(delta, "content")
            if isinstance(content, str) and content:
                pending = marker_tail + content
                marker_tail = ""
                while pending:
                    marker = self._THINK_END if in_reasoning else self._THINK_START
                    marker_at = pending.find(marker)
                    if marker_at >= 0:
                        segment = pending[:marker_at]
                        if segment:
                            yield self._event(
                                "ReasoningDelta" if in_reasoning else "TextDelta",
                                {"text": segment},
                            )
                        in_reasoning = not in_reasoning
                        pending = pending[marker_at + len(marker) :]
                        continue

                    partial_size = _partial_marker_suffix_length(pending, marker)
                    segment = pending[:-partial_size] if partial_size else pending
                    if segment:
                        yield self._event(
                            "ReasoningDelta" if in_reasoning else "TextDelta",
                            {"text": segment},
                        )
                    if partial_size:
                        marker_tail = pending[-partial_size:]
                    break

            for item in _mapping_value(delta, "tool_calls") or []:
                index = int(_mapping_value(item, "index") or 0)
                call = tool_calls.setdefault(
                    index, {"id": "", "name": "", "arguments": ""}
                )
                item_id = _mapping_value(item, "id")
                if isinstance(item_id, str) and item_id and not call["id"]:
                    call["id"] = item_id
                call["id"] = call["id"] or f"openai-tool-{index}"
                function = _mapping_value(item, "function")
                name = _mapping_value(function, "name") if function else ""
                arguments = _mapping_value(function, "arguments") if function else ""
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

        if marker_tail:
            yield self._event(
                "ReasoningDelta" if in_reasoning else "TextDelta",
                {"text": marker_tail},
            )
        yield from self._complete_tools(tool_calls)
        yield self._event("ResponseCompleted", {})

    @classmethod
    def _split_think_text(cls, text: str) -> tuple[str, str]:
        """Split complete ``<think>`` blocks from visible assistant text."""

        reasoning_parts: list[str] = []
        visible_parts: list[str] = []
        pending = text
        in_reasoning = False

        while pending:
            marker = cls._THINK_END if in_reasoning else cls._THINK_START
            marker_at = pending.find(marker)
            if marker_at < 0:
                (reasoning_parts if in_reasoning else visible_parts).append(pending)
                break
            segment = pending[:marker_at]
            if segment:
                (reasoning_parts if in_reasoning else visible_parts).append(segment)
            in_reasoning = not in_reasoning
            pending = pending[marker_at + len(marker) :]

        return "".join(reasoning_parts), "".join(visible_parts)


__all__ = ["FoundryLocalRuntime"]

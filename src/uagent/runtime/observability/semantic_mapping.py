"""OpenTelemetry-specific semantic mapping for UAG operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MappedSpan:
    name: str
    attributes: dict[str, Any]


def map_span(
    operation: str,
    attributes: Mapping[str, Any] | None = None,
) -> MappedSpan:
    """Project one UAG operation into OTel span naming/attributes.

    Runtime code supplies UAG-owned operation names and metadata. GenAI semantic
    convention details stay here so future convention changes do not leak into
    the rest of the runtime.
    """

    op = str(operation or "uag.operation").strip() or "uag.operation"
    attrs = dict(attributes or {})
    mapped = dict(attrs)

    if op == "invoke_agent":
        agent_name = str(attrs.get("uag.agent.name") or "uag")
        mapped.setdefault("gen_ai.operation.name", "invoke_agent")
        mapped.setdefault("gen_ai.agent.name", agent_name)
        return MappedSpan(f"invoke_agent {agent_name}", mapped)

    if op == "chat":
        model = str(attrs.get("uag.llm.model") or "").strip()
        provider = str(attrs.get("uag.llm.provider") or "").strip()
        mapped.setdefault("gen_ai.operation.name", "chat")
        if model:
            mapped.setdefault("gen_ai.request.model", model)
        if provider:
            mapped.setdefault("gen_ai.provider.name", provider)
        return MappedSpan(f"chat {model}" if model else "chat", mapped)

    if op == "execute_tool":
        tool_name = str(attrs.get("uag.tool.name") or "").strip()
        mapped.setdefault("gen_ai.operation.name", "execute_tool")
        return MappedSpan(
            f"execute_tool {tool_name}" if tool_name else "execute_tool", mapped
        )

    return MappedSpan(op, mapped)


__all__ = ["MappedSpan", "map_span"]

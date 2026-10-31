"""OpenTelemetry-specific semantic mapping for UAG operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# Project internal aliases to standard OTel attributes only at the adapter boundary.
_STANDARD_ATTRIBUTE_ALIASES = {
    "uag.agent.name": "gen_ai.agent.name",
    "uag.llm.model": "gen_ai.request.model",
    "uag.tool.name": "gen_ai.tool.name",
    "uag.tokens.reported.input": "gen_ai.usage.input_tokens",
    "uag.tokens.reported.output": "gen_ai.usage.output_tokens",
    "uag.error.type": "error.type",
}
_SPAN_DERIVED_ATTRIBUTES = frozenset(
    {
        "uag.status",  # OTel span status.
        "uag.duration_ms",  # OTel span start/end timestamps.
        "uag.tokens.reported.total",  # Derived from input/output token usage.
    }
)
_USAGE_ALIASES = frozenset({"uag.tokens.reported.input", "uag.tokens.reported.output"})

_GENAI_PROVIDER_NAMES = {
    "azure": "azure.ai.openai",
    "bedrock": "aws.bedrock",
    "claude": "anthropic",
    "deepseek": "deepseek",
    "gemini": "gcp.gemini",
    "grok": "x_ai",
    "moonshot": "moonshot_ai",
    "openai": "openai",
    "vertexai": "gcp.vertex_ai",
}


def _genai_provider_name(provider: str) -> str:
    original = str(provider or "").strip()
    normalized = original.lower()
    return _GENAI_PROVIDER_NAMES.get(normalized, original)


def map_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    """Export standard attributes without duplicating UAG aliases.

    Explicit standard attributes take precedence. Estimated tokens and other
    UAG-only metadata retain their separate meanings.
    """

    source = dict(attributes or {})
    mapped = {
        key: value
        for key, value in source.items()
        if key not in _STANDARD_ATTRIBUTE_ALIASES
        and key != "uag.llm.provider"
        and key not in _SPAN_DERIVED_ATTRIBUTES
    }
    for key, value in source.items():
        target = (
            "gen_ai.provider.name"
            if key == "uag.llm.provider"
            else _STANDARD_ATTRIBUTE_ALIASES.get(key)
        )
        if not target or target in mapped:
            continue
        if key == "uag.llm.provider":
            value = _genai_provider_name(value)
            if not value:
                continue
        elif key in _USAGE_ALIASES and (type(value) is not int or value < 0):
            # Standard GenAI usage counts must be non-negative integers.
            continue
        mapped[target] = value
    return mapped


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
    mapped = map_attributes(attrs)

    if op == "invoke_agent":
        agent_name = str(attrs.get("uag.agent.name") or "uag")
        mapped.setdefault("gen_ai.operation.name", "invoke_agent")
        mapped.setdefault("gen_ai.agent.name", agent_name)
        return MappedSpan(f"invoke_agent {agent_name}", mapped)

    if op == "chat":
        model = str(attrs.get("uag.llm.model") or "").strip()
        provider = str(attrs.get("uag.llm.provider") or "").strip()
        semantic_provider = _genai_provider_name(provider)
        mapped.setdefault("gen_ai.operation.name", "chat")
        if model:
            mapped.setdefault("gen_ai.request.model", model)
        if semantic_provider:
            mapped.setdefault("gen_ai.provider.name", semantic_provider)
        return MappedSpan(f"chat {model}" if model else "chat", mapped)

    if op == "execute_tool":
        tool_name = str(attrs.get("uag.tool.name") or "").strip()
        mapped.setdefault("gen_ai.operation.name", "execute_tool")
        if tool_name:
            mapped.setdefault("gen_ai.tool.name", tool_name)
        return MappedSpan(
            f"execute_tool {tool_name}" if tool_name else "execute_tool", mapped
        )

    if op == "provider_sdk":
        provider_id = attrs.get("uag.provider.id")
        if type(provider_id) is str and provider_id in {"openai", "claude"}:
            return MappedSpan("provider_sdk", {"uag.provider.id": provider_id})
        return MappedSpan("provider_sdk", {})

    return MappedSpan(op, mapped)


__all__ = ["MappedSpan", "map_attributes", "map_span"]

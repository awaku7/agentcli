"""Transport-specific Chat Completions tool selection policy.

This module owns the OpenAI Chat Completions tool-count constraint while
keeping the historical helper import path as a compatibility surface.
"""

from __future__ import annotations

from typing import Any

from .context_budget import ContextBudget
from .context_tools import select_tool_definitions

CHAT_COMPLETIONS_MAX_TOOLS = 128
CHAT_TOOL_HELPERS = frozenset(
    {"tool_catalog", "tool_load", "unload_tool", "human_ask"}
)


def _tool_spec_name(spec: Any) -> str:
    function = spec.get("function") if isinstance(spec, dict) else None
    return str(function.get("name") or "").strip() if isinstance(function, dict) else ""


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages or []):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"].strip())
            if parts:
                return "\n".join(part for part in parts if part)
    return ""


def limit_chat_completion_tools(
    tool_specs: Any, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Keep Chat Completions requests within the provider tool-count limit."""
    specs = [spec for spec in (tool_specs or []) if isinstance(spec, dict)]
    if len(specs) <= CHAT_COMPLETIONS_MAX_TOOLS:
        return specs

    selected: list[dict[str, Any]] = []
    try:
        selected = select_tool_definitions(
            specs,
            task=_latest_user_text(messages),
            budget=ContextBudget.without_limit(),
            max_tools=CHAT_COMPLETIONS_MAX_TOOLS,
        ).specs
    except Exception:
        selected = []

    selected_names = {_tool_spec_name(spec) for spec in selected}
    helper_specs = [
        spec for spec in specs if _tool_spec_name(spec) in CHAT_TOOL_HELPERS
    ]
    selected_names.update(_tool_spec_name(spec) for spec in helper_specs)
    result: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for spec in helper_specs:
        result.append(spec)
        seen_ids.add(id(spec))
    for spec in specs:
        if _tool_spec_name(spec) in selected_names and id(spec) not in seen_ids:
            result.append(spec)
            seen_ids.add(id(spec))
        if len(result) >= CHAT_COMPLETIONS_MAX_TOOLS:
            break
    if len(result) < CHAT_COMPLETIONS_MAX_TOOLS:
        for spec in specs:
            if id(spec) not in seen_ids:
                result.append(spec)
                seen_ids.add(id(spec))
            if len(result) >= CHAT_COMPLETIONS_MAX_TOOLS:
                break
    return result[:CHAT_COMPLETIONS_MAX_TOOLS]


def initial_chat_completion_tools(tool_specs: Any) -> list[dict[str, Any]]:
    """Return discovery tools for the first Chat Completions round."""
    specs = [spec for spec in (tool_specs or []) if isinstance(spec, dict)]
    initial = [
        spec
        for spec in specs
        if _tool_spec_name(spec) in {"tool_catalog", "tool_load", "unload_tool"}
    ]
    return initial or limit_chat_completion_tools(specs, [])

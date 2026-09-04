"""DeepSeek Responses API compatibility and history helpers."""

from __future__ import annotations

import json
from typing import Any


def apply_deepseek_responses_compat(
    resp_kwargs: dict[str, Any], *, provider: str, depname: str
) -> None:
    """Remove Responses parameters unsupported by DeepSeek."""
    if provider != "deepseek":
        return
    resp_kwargs.pop("context_management", None)
    text_cfg = resp_kwargs.get("text")
    if isinstance(text_cfg, dict):
        text_cfg.pop("verbosity", None)
        if not text_cfg:
            resp_kwargs.pop("text", None)


def normalize_deepseek_responses_effort(
    effort: str, *, provider: str, depname: str
) -> str:
    """Map a generic reasoning effort to DeepSeek's Responses values."""
    if provider != "deepseek":
        return effort
    try:
        from .llm_deepseek import _get_valid_deepseek_efforts, _resolve_deepseek_effort

        mapped = _resolve_deepseek_effort(effort)
        if mapped:
            valid = _get_valid_deepseek_efforts(depname)
            if valid and mapped not in valid:
                mapped = "high" if "high" in valid else sorted(valid)[0]
            return mapped
    except Exception:
        pass
    return effort


def assistant_tool_turn_items(
    message: dict[str, Any], *, provider: str
) -> list[dict[str, Any]] | None:
    """Return DeepSeek-specific assistant tool items, or ``None`` otherwise."""
    if provider != "deepseek":
        return None
    return function_call_items(message)


def tool_turn_item(
    message: dict[str, Any], *, provider: str
) -> tuple[bool, dict[str, Any] | None]:
    """Return whether the tool turn is DeepSeek-specific and its output item."""
    if provider != "deepseek":
        return False, None
    return True, function_call_output_item(message)


def function_call_items(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a Chat-Completions assistant tool turn to Responses items."""
    result: list[dict[str, Any]] = []
    for tc in message.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function")
        fn = fn if isinstance(fn, dict) else {}
        call_id = tc.get("id") or tc.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            continue
        arguments = fn.get("arguments", tc.get("arguments", "{}"))
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        result.append(
            {
                "type": "function_call",
                "call_id": call_id,
                "name": str(fn.get("name") or tc.get("name") or "unknown"),
                "arguments": str(arguments or "{}"),
            }
        )
    return result


def function_call_output_item(message: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a Chat-Completions tool message to a DeepSeek Responses item."""
    call_id = message.get("tool_call_id") or message.get("id")
    if not isinstance(call_id, str) or not call_id:
        return None
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": str(message.get("content", "")),
    }

"""Shared tool-execution boundary for legacy provider rounds."""

from __future__ import annotations

from typing import Any


def execute_legacy_tool_calls(
    *,
    tool_calls: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    core: Any,
    cache_mgr: Any = None,
    responses_api_continuation: bool = False,
    judgment_mode: bool = False,
) -> tuple[bool, list[dict[str, Any]]]:
    """Execute one legacy round's collected tool calls exactly once.

    Judgment mode must remain side-effect free. Empty tool-call lists are a
    no-op so every legacy provider can use this boundary unconditionally.
    """
    if judgment_mode or not tool_calls:
        return False, []

    from ..llm_flow_helpers import _execute_tool_calls

    return _execute_tool_calls(
        tool_calls_list=tool_calls,
        messages=messages,
        core=core,
        cache_mgr=cache_mgr,
        responses_api_continuation=responses_api_continuation,
        responses_runtime=getattr(core, "responses_runtime", None),
    )


__all__ = ["execute_legacy_tool_calls"]

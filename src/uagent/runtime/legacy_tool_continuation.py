"""Shared tool-execution boundary for legacy provider rounds."""

from __future__ import annotations

from typing import Any


def execute_tool_continuation(
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    tool_calls_list: list[dict[str, Any]] | None = None,
    messages: list[dict[str, Any]],
    core: Any,
    cache_mgr: Any = None,
    responses_api_continuation: bool = False,
    responses_runtime: Any = None,
    judgment_mode: bool = False,
) -> tuple[bool, list[dict[str, Any]]]:
    """Execute one legacy round's collected tool calls exactly once.

    Judgment mode must remain side-effect free. Empty tool-call lists are a
    no-op so every legacy provider can use this boundary unconditionally.
    """
    tool_calls = tool_calls if tool_calls is not None else (tool_calls_list or [])
    if judgment_mode or not tool_calls:
        return False, []

    from ..llm_flow_helpers import _execute_tool_calls

    return _execute_tool_calls(
        tool_calls_list=tool_calls,
        messages=messages,
        core=core,
        cache_mgr=cache_mgr,
        responses_api_continuation=responses_api_continuation,
        responses_runtime=(
            responses_runtime
            if responses_runtime is not None
            else getattr(core, "responses_runtime", None)
        ),
    )


def execute_legacy_tool_calls(**kwargs: Any) -> tuple[bool, list[dict[str, Any]]]:
    """Backward-compatible name for legacy provider adapters."""
    return execute_tool_continuation(**kwargs)


__all__ = ["execute_legacy_tool_calls", "execute_tool_continuation"]

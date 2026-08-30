"""Validated direct execution of a scheduled UAG tool."""

from __future__ import annotations

import json
from typing import Any

# Direct jobs must not become an arbitrary-code execution escape hatch.  These
# tools can execute arbitrary code/processes or manage the scheduler/tool
# registry itself and therefore require a separately designed workflow type.
_DIRECT_JOB_DENIED_TOOLS = frozenset(
    {
        "tool_catalog",
        "tool_load",
        "unload_tool",
        "python_exec",
        "bash_exec",
        "cmd_exec_json",
        "pwsh_exec",
        "spawn_process",
        "system_reload",
        "set_timer",
    }
)


def execute_direct_tool(tool_name: object, arguments: object) -> Any:
    """Run one explicitly named tool and normalize its result.

    The common tool dispatcher remains responsible for policy checks and lazy
    loading.  This layer adds the scheduler-specific boundary: only a single
    explicitly named tool is allowed, and management/arbitrary-code tools are
    rejected.
    """
    name = str(tool_name or "").strip()
    if not name:
        raise ValueError("direct scheduled job requires target_tool")
    if name in _DIRECT_JOB_DENIED_TOOLS:
        raise ValueError(f"tool is not allowed for direct scheduled jobs: {name}")
    if not isinstance(arguments, dict):
        raise ValueError("direct scheduled job target_args must be an object")

    from .. import tools

    raw = tools.run_tool(name, dict(arguments))
    if not isinstance(raw, str):
        return raw
    stripped = raw.strip()
    if stripped.startswith(("[tool error]", "[tool argument error]", "[tool policy]")):
        raise RuntimeError(stripped)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if isinstance(parsed, dict) and parsed.get("ok") is False:
        raise RuntimeError(str(parsed.get("error") or "direct tool failed"))
    return parsed


__all__ = ["execute_direct_tool"]

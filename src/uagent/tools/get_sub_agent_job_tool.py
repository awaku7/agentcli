"""Inspect one owner-scoped background Sub-Agent Job."""

from __future__ import annotations

from typing import Any

from ._sub_agent_job_tools_common import blocked, get_job_runtime, json_result
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_level": 0,
    "function": {
        "name": "get_sub_agent_job",
        "description": _(
            "tool.description",
            default="Get the current state and result of a background Sub-Agent Job without waiting.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["get_sub_agent_job", "job status", "subagent status"],
        ),
        "x_search_terms_en": ["get_sub_agent_job", "job status", "subagent status"],
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": _(
                        "param.job_id.description",
                        default="Job ID returned by spawn_sub_agent.",
                    ),
                }
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    runtime = get_job_runtime()
    if runtime is None:
        return blocked("cli_foreground_main_only")
    manager, owner = runtime
    job_id = str(args.get("job_id") or "").strip()
    if not job_id:
        return blocked("invalid_job_id")
    return json_result(manager.get(owner=owner, job_id=job_id))

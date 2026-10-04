"""Send bounded inbox instructions to an active background Sub-Agent Job."""

from __future__ import annotations

from typing import Any

from ._sub_agent_job_tools_common import blocked, get_job_runtime, json_result
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_level": 0,
    "function": {
        "name": "send_sub_agent_message",
        "description": _(
            "tool.description",
            default="Send additional instructions to a running Sub-Agent Job. They are delivered at a safe round boundary, not injected into an active provider call.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["send_sub_agent_message", "message subagent", "job inbox"],
        ),
        "x_search_terms_en": [
            "send_sub_agent_message",
            "message subagent",
            "job inbox",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": _(
                        "param.job_id.description",
                        default="Job ID returned by spawn_sub_agent.",
                    ),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Additional instruction for the Sub-Agent.",
                    ),
                },
            },
            "required": ["job_id", "message"],
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
    return json_result(
        manager.send_message(
            owner=owner, job_id=job_id, message=str(args.get("message") or "")
        )
    )

"""Wait for a background Sub-Agent Job while preserving F12 interruption."""

from __future__ import annotations

import time
from typing import Any

from ._sub_agent_job_tools_common import blocked, get_job_runtime, json_result
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_level": 0,
    "function": {
        "name": "wait_sub_agent_job",
        "description": _(
            "tool.description",
            default="Wait for a background Sub-Agent Job to finish. This is a foreground wait and can be interrupted without cancelling the Job.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["wait_sub_agent_job", "join subagent", "wait for job"],
        ),
        "x_search_terms_en": ["wait_sub_agent_job", "join subagent", "wait for job"],
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
                "timeout": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 86400,
                    "default": 60,
                    "description": _(
                        "param.timeout.description",
                        default="Maximum seconds to wait. The Job continues running if this wait times out.",
                    ),
                },
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
    },
}


def _interrupted() -> bool:
    try:
        from .. import core

        return bool(getattr(core, "interrupt_requested", False))
    except Exception:
        return False


def run_tool(args: dict[str, Any]) -> str:
    runtime = get_job_runtime()
    if runtime is None:
        return blocked("foreground_main_agent_only")
    manager, owner = runtime
    job_id = str(args.get("job_id") or "").strip()
    if not job_id:
        return blocked("invalid_job_id")
    try:
        timeout = max(0.0, min(86400.0, float(args.get("timeout", 60))))
    except (TypeError, ValueError):
        return blocked("invalid_timeout")

    deadline = time.monotonic() + timeout
    while True:
        result = manager.wait(
            owner=owner,
            job_id=job_id,
            timeout=min(0.25, max(0.0, deadline - time.monotonic())),
        )
        if result.get("state") in {
            "completed",
            "blocked",
            "failed",
            "cancelled",
            "timed_out",
        }:
            return json_result(result)
        if result.get("reason") == "not_found":
            return json_result(result)
        if _interrupted():
            result["wait_interrupted"] = True
            result["job_continues"] = True
            return json_result(result)
        if time.monotonic() >= deadline:
            result["wait_timed_out"] = True
            return json_result(result)

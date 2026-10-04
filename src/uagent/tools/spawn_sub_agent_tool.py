"""Spawn a CLI-owned Sub-Agent as a bounded background Job."""

from __future__ import annotations

import os
from typing import Any

from ._sub_agent_job_tools_common import (
    blocked,
    get_job_runtime,
    json_result,
    namespace_shared_context,
)
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_level": 0,
    "function": {
        "name": "spawn_sub_agent",
        "description": _(
            "tool.description",
            default="Start a Sub-Agent in the background and return its Job ID immediately. Use the Job tools to inspect, message, wait for, or cancel it.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "spawn_sub_agent",
                "background subagent",
                "start job",
                "delegate job",
            ],
        ),
        "x_search_terms_en": [
            "spawn_sub_agent",
            "background subagent",
            "start job",
            "delegate job",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": _(
                        "param.agent_name.description",
                        default="Built-in Sub-Agent role, such as planner or reviewer.",
                    ),
                },
                "task": {
                    "type": "string",
                    "description": _(
                        "param.task.description",
                        default="The work instruction for the Sub-Agent.",
                    ),
                },
                "provider": {
                    "type": "string",
                    "description": _(
                        "param.provider.description",
                        default="Optional provider override.",
                    ),
                },
                "model": {
                    "type": "string",
                    "description": _(
                        "param.model.description", default="Optional model override."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": _(
                        "param.reasoning.description",
                        default="Optional reasoning-effort override.",
                    ),
                },
                "permission_level": {
                    "type": "string",
                    "enum": ["none"],
                    "default": "none",
                    "description": _(
                        "param.permission_level.description",
                        default="Background V1 only permits none until each tool has passed the background safety audit.",
                    ),
                },
                "max_tool_turns": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 12,
                    "default": 3,
                },
                "max_agent_rounds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 3,
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 86400,
                    "default": 300,
                    "description": _(
                        "param.timeout.description",
                        default="Absolute end-to-end Job deadline in seconds, including queue time.",
                    ),
                },
                "parent_goal": {
                    "type": "string",
                    "description": _(
                        "param.parent_goal.description",
                        default="Optional parent goal for the Sub-Agent context.",
                    ),
                },
                "store_key": {
                    "type": "string",
                    "description": _(
                        "param.store_key.description",
                        default="Optional owner-scoped key for the approved Job result.",
                    ),
                },
                "load_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.load_keys.description",
                        default="Optional owner-scoped shared-result keys to load into context.",
                    ),
                },
            },
            "required": ["agent_name", "task"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    runtime = get_job_runtime()
    if runtime is None:
        return blocked("foreground_main_agent_only")
    manager, owner = runtime

    agent_name = str(args.get("agent_name") or "").strip()
    task = str(args.get("task") or "")
    if not agent_name or not task.strip():
        return blocked(
            "invalid_request", "agent_name and a non-empty task are required"
        )
    if str(args.get("permission_level") or "none") != "none":
        return blocked("background_tool_permission_not_audited")

    load_keys = args.get("load_keys") or []
    if not isinstance(load_keys, list) or any(
        not isinstance(k, str) for k in load_keys
    ):
        return blocked("invalid_load_keys")
    shared_context, missing_keys = manager.load_shared_results(
        owner=owner, keys=load_keys
    )
    if missing_keys:
        return blocked(
            "shared_keys_not_found", json_result({"missing_keys": missing_keys})
        )
    try:
        shared_context = namespace_shared_context(shared_context)
    except ValueError as exc:
        return blocked(str(exc))

    options = {
        "agent_name": agent_name,
        "task": task,
        "provider": args.get("provider"),
        "model": args.get("model"),
        "reasoning": args.get("reasoning"),
        "permission_level": "none",
        "max_tool_turns": int(args.get("max_tool_turns", 3)),
        "max_agent_rounds": int(args.get("max_agent_rounds", 3)),
        "timeout": 120,
        "parent_goal": args.get("parent_goal"),
        "_shared_context": shared_context,
    }
    # The manager supplies a fixed workdir snapshot; callers cannot select a
    # different filesystem root through tool arguments.
    store_key = str(args.get("store_key") or "").strip() or None

    def worker(job_context):
        from .sub_agent_tool import run_tool as run_sync_sub_agent

        job_context.raise_if_cancelled()
        messages = job_context.drain_messages()
        worker_task = task
        previous = getattr(worker_state, "previous_result", "")
        if previous:
            worker_task += "\n\n[Previous Job result]\n" + previous[:16000]
        if messages:
            worker_task += "\n\n[New instructions from Main Agent]\n" + "\n".join(
                f"(message {item['sequence']}) {item['message']}" for item in messages
            )
        if (
            len(worker_task.encode("utf-8", errors="replace"))
            > manager.settings.task_max_bytes
        ):
            return json_result(
                {"status": "blocked", "reason": "job_instruction_context_too_large"}
            )
        per_call_remaining = job_context.remaining
        if per_call_remaining is not None:
            options["timeout"] = max(1, int(per_call_remaining))
        options["task"] = worker_task
        result = run_sync_sub_agent(dict(options))
        job_context.raise_if_cancelled()
        worker_state.previous_result = result
        return result

    class _WorkerState:
        previous_result = ""

    worker_state = _WorkerState()
    return json_result(
        manager.spawn(
            owner=owner,
            agent_name=agent_name,
            task=task,
            worker=worker,
            job_root=os.getcwd(),
            timeout=float(args.get("timeout", 300)),
            store_key=store_key,
        )
    )

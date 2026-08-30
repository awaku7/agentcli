from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import uuid4

from ..scheduler import (
    SCHEDULE_TYPE_ONCE,
    ScheduleItem,
    SchedulerStore,
    format_iso_datetime,
    utc_now,
)
from .i18n_helper import make_tool_translator
from .os_scheduler_helper import (
    create_os_schedule,
    delete_os_schedule,
    list_os_schedules,
)

_ = make_tool_translator(__file__)

BUSY_LABEL = False

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "set_timer",
        "description": _(
            "tool.description",
            default="Displays a message after a specified number of seconds. Optionally, an automatic message can be input into the LLM. Supports OS-level scheduling (schtasks/at) with os_persist=True.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "set_timer",
                "set timer",
                "timer",
                "reminder",
                "alarm",
                "delay",
                "os schedule",
                "schtasks",
                "cron",
            ],
        ),
        "x_search_terms_en": [
            "set_timer",
            "set timer",
            "timer",
            "reminder",
            "alarm",
            "delay",
            "os schedule",
            "schtasks",
            "cron",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "delete", "list"],
                    "description": _(
                        "param.action.description",
                        default="Action to perform: create (default), delete, or list.",
                    ),
                },
                "seconds": {
                    "type": "integer",
                    "description": _(
                        "param.seconds.description",
                        default="Timer duration in seconds (required for action=create).",
                    ),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Message to display upon completion.",
                    ),
                },
                "on_timeout_prompt": {
                    "type": "string",
                    "description": _(
                        "param.on_timeout_prompt.description",
                        default="Automatic input for the LLM upon timeout.",
                    ),
                    "nullable": True,
                },
                "os_persist": {
                    "type": "boolean",
                    "description": _(
                        "param.os_persist.description",
                        default="Register with the OS scheduler (schtasks on Windows, at on Linux/macOS). Timer fires even if uag is not running.",
                    ),
                },
                "job_name": {
                    "type": "string",
                    "description": _(
                        "param.job_name.description",
                        default="Job name (required for OS action=delete, auto-generated for OS action=create).",
                    ),
                },
                "schedule_id": {
                    "type": "string",
                    "description": _(
                        "param.schedule_id.description",
                        default="Internal schedule ID (required to delete an in-process timer).",
                    ),
                },
                "required_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.required_tools.description",
                        default="Tool names that must be loaded and protected while this timer's LLM run executes.",
                    ),
                },
                "execution_mode": {
                    "type": "string",
                    "enum": ["llm", "direct"],
                    "description": _(
                        "param.execution_mode.description",
                        default="Run through the LLM (llm) or execute one explicit tool directly (direct).",
                    ),
                },
                "target_tool": {
                    "type": "string",
                    "description": _(
                        "param.target_tool.description",
                        default="Tool name for execution_mode=direct, for example 'excel_ops'.",
                    ),
                },
                "target_args": {
                    "type": "object",
                    "description": _(
                        "param.target_args.description",
                        default="Arguments passed to target_tool for execution_mode=direct.",
                    ),
                },
            },
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "create").strip().lower()

    if action == "list":
        return _run_list()

    if action == "delete":
        return _run_delete(args)

    return _run_create(args)


def _run_create(args: dict[str, Any]) -> str:
    raw_seconds = args.get("seconds", 0)

    try:
        seconds = int(raw_seconds)
    except Exception:
        return _(
            "err.seconds_invalid",
            default="[set_timer error] seconds could not be interpreted as an integer: {raw}",
        ).format(raw=repr(raw_seconds))

    if seconds < 0:
        return _(
            "err.seconds_negative",
            default="[set_timer error] seconds must be 0 or greater: {val}",
        ).format(val=seconds)

    raw_message = args.get("message")
    message = (
        _("msg.default_timer_done", default="Timer finished")
        if raw_message is None
        else str(raw_message)
    )
    on_timeout_prompt = args.get("on_timeout_prompt")
    llm_prompt = "" if on_timeout_prompt is None else str(on_timeout_prompt)
    raw_required_tools = args.get("required_tools") or []
    if isinstance(raw_required_tools, str):
        required_tools = (
            [raw_required_tools.strip()] if raw_required_tools.strip() else []
        )
    elif isinstance(raw_required_tools, (list, tuple, set, frozenset)):
        required_tools = [
            str(name).strip() for name in raw_required_tools if str(name).strip()
        ]
    else:
        required_tools = []

    execution_mode = str(args.get("execution_mode") or "llm").strip().lower()
    if execution_mode not in {"llm", "direct"}:
        return _(
            "err.execution_mode_invalid",
            default="[set_timer error] execution_mode must be 'llm' or 'direct'",
        )
    target_tool = str(args.get("target_tool") or "").strip()
    target_args = args.get("target_args") or {}
    if isinstance(target_args, str):
        try:
            target_args = json.loads(target_args)
        except (TypeError, ValueError):
            return _(
                "err.target_args_json",
                default="[set_timer error] target_args must be a JSON object",
            )
    if not isinstance(target_args, dict):
        return _(
            "err.target_args_type",
            default="[set_timer error] target_args must be an object",
        )
    if execution_mode == "direct" and not target_tool:
        return _(
            "err.target_tool_required",
            default="[set_timer error] target_tool is required for execution_mode=direct",
        )

    os_persist = bool(args.get("os_persist", False))

    if os_persist:
        if execution_mode == "direct":
            return _(
                "err.direct_os_persist",
                default="[set_timer error] direct execution is not supported with os_persist=True",
            )
        return _run_create_os(seconds, message, llm_prompt)
    return _run_create_internal(
        seconds,
        message,
        llm_prompt,
        required_tools,
        execution_mode=execution_mode,
        target_tool=target_tool,
        target_args=target_args,
    )


def _run_create_internal(
    seconds: int,
    message: str,
    llm_prompt: str,
    required_tools: list[str],
    *,
    execution_mode: str = "llm",
    target_tool: str = "",
    target_args: dict[str, Any] | None = None,
) -> str:
    schedule = ScheduleItem(
        id=str(uuid4()),
        type=SCHEDULE_TYPE_ONCE,
        at=format_iso_datetime(utc_now() + timedelta(seconds=seconds)),
        message=message,
        llm_prompt=llm_prompt,
        interval_sec=0,
        required_tools=required_tools,
        execution_mode=execution_mode,
        target_tool=target_tool,
        target_args=dict(target_args or {}),
        enabled=True,
    )
    SchedulerStore().add_item(schedule)

    return _(
        "out.ok_internal",
        default="[set_timer] Timer set for {seconds} seconds: {message} (schedule_id={schedule_id}, on_timeout_prompt={prompt})",
    ).format(
        seconds=seconds,
        message=message,
        schedule_id=schedule.id,
        prompt=repr(llm_prompt or None),
    )


def _run_create_os(seconds: int, message: str, llm_prompt: str) -> str:
    from ..env_utils import env_get
    import os as _os

    at_dt = utc_now() + timedelta(seconds=seconds)
    workdir = env_get("UAGENT_WORKDIR") or _os.getcwd()
    # Collect loaded tool names from TOOL_SPECS
    from .. import tools as _tools

    tool_names = [
        str(s.get("function", {}).get("name", ""))
        for s in getattr(_tools, "TOOL_SPECS", [])
        if s.get("function", {}).get("name")
    ]
    tool_names.sort()

    result = create_os_schedule(
        at_dt=at_dt,
        enable_tools=tool_names,
        message=message,
        on_timeout_prompt=llm_prompt,
        workdir=workdir,
    )

    if result.get("ok"):
        return _(
            "out.ok_os",
            default="[set_timer] OS schedule created: {job_name}. Fires at {at}. Command: {cmd}",
        ).format(
            job_name=result["job_name"],
            at=format_iso_datetime(at_dt),
            cmd=result.get("raw_output", ""),
        )
    else:
        return _(
            "err.os_schedule_failed",
            default="[set_timer error] Failed to create OS schedule: {msg}",
        ).format(msg=result.get("message", "Unknown error"))


def _run_delete(args: dict[str, Any]) -> str:
    schedule_id = str(args.get("schedule_id") or "").strip()
    if schedule_id:
        deleted = SchedulerStore().delete_item(schedule_id)
        if deleted:
            return _(
                "out.internal_delete_ok",
                default="[set_timer] Internal schedule deleted: {schedule_id}",
            ).format(schedule_id=schedule_id)
        return _(
            "err.internal_delete_not_found",
            default="[set_timer error] Internal schedule not found: {schedule_id}",
        ).format(schedule_id=schedule_id)

    job_name = str(args.get("job_name") or "").strip()
    if not job_name:
        return _(
            "err.job_name_required",
            default="[set_timer error] job_name is required for action=delete.",
        )

    result = delete_os_schedule(job_name)

    if result.get("ok"):
        return _(
            "out.delete_ok",
            default="[set_timer] OS schedule deleted: {job_name}",
        ).format(job_name=job_name)
    else:
        return _(
            "err.delete_failed",
            default="[set_timer error] Failed to delete OS schedule: {msg}",
        ).format(msg=result.get("message", "Unknown error"))


def _run_list() -> str:
    internal = SchedulerStore().list_items()
    os_schedules = list_os_schedules()
    if not internal and not os_schedules:
        return _(
            "out.list_empty",
            default="[set_timer] No schedules found.",
        )

    lines: list[str] = [_("out.list_header", default="[set_timer] Schedules:")]
    for item in internal:
        lines.append(
            _(
                "out.list_internal_item",
                default="  - internal: {schedule_id} at {at} ({mode})",
            ).format(schedule_id=item.id, at=item.at, mode=item.execution_mode)
        )
    for schedule in os_schedules:
        lines.append(
            _(
                "out.list_os_item",
                default="  - OS: {job_name}",
            ).format(job_name=schedule.get("job_name", "?"))
        )
    return "\n".join(lines)

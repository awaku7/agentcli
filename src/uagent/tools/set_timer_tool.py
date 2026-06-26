from __future__ import annotations

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
                        default="Job name (required for action=delete, auto-generated for action=create).",
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

    os_persist = bool(args.get("os_persist", False))

    if os_persist:
        return _run_create_os(seconds, message, llm_prompt)
    else:
        return _run_create_internal(seconds, message, llm_prompt)


def _run_create_internal(seconds: int, message: str, llm_prompt: str) -> str:
    schedule = ScheduleItem(
        id=str(uuid4()),
        type=SCHEDULE_TYPE_ONCE,
        at=format_iso_datetime(utc_now() + timedelta(seconds=seconds)),
        message=message,
        llm_prompt=llm_prompt,
        interval_sec=0,
        enabled=True,
    )
    SchedulerStore().add_item(schedule)

    return _(
        "out.ok",
        default="[set_timer] Timer set for {seconds} seconds: {message} (on_timeout_prompt={prompt})",
    ).format(seconds=seconds, message=message, prompt=repr(llm_prompt or None))


def _run_create_os(seconds: int, message: str, llm_prompt: str) -> str:
    from ..env_utils import env_get
    import os as _os

    at_dt = utc_now() + timedelta(seconds=seconds)
    workdir = env_get("UAGENT_WORKDIR") or _os.getcwd()

    result = create_os_schedule(
        at_dt=at_dt,
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
    schedules = list_os_schedules()
    if not schedules:
        return _(
            "out.list_empty",
            default="[set_timer] No OS schedules found.",
        )

    lines: list[str] = [
        _("out.list_header", default="[set_timer] OS schedules:")
    ]
    for s in schedules:
        lines.append(f"  - {s.get('job_name', '?')}")
    return "\n".join(lines)

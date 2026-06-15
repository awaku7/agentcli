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

_ = make_tool_translator(__file__)

BUSY_LABEL = False

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "set_timer",
        "description": _(
            "tool.description",
            default="Displays a message after a specified number of seconds. Optionally, an automatic message can be input into the LLM.",
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
            ],
        ),
        "x_search_terms_en": [
            "set_timer",
            "set timer",
            "timer",
            "reminder",
            "alarm",
            "delay",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": _(
                        "param.seconds.description",
                        default="Timer duration in seconds.",
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
            },
            "required": ["seconds"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
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
    ).format(seconds=seconds, message=message, prompt=repr(on_timeout_prompt))

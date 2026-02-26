# tools/set_timer.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict
import threading
import time

from .context import get_callbacks

BUSY_LABEL = False

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "set_timer",
        "description": _(
            "tool.description",
            default="Displays a message after a specified number of seconds. Optionally, an automatic message can be input into the LLM.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool is used for the following purpose: display a message after a specified number of seconds and optionally input an automatic message to the LLM.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": _("param.seconds.description", default="Timer duration in seconds."),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description", default="Message to display upon completion."
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


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    raw_seconds = args.get("seconds", 0)

    try:
        seconds = int(raw_seconds)
    except Exception:
        return _("err.seconds_invalid", default="[set_timer error] seconds could not be interpreted as an integer: {raw}").format(raw=repr(raw_seconds))

    if seconds < 0:
        return _("err.seconds_negative", default="[set_timer error] seconds must be 0 or greater: {val}").format(val=seconds)

    message = args.get("message", _("msg.default_timer_done", default="Timer finished"))
    on_timeout_prompt = args.get("on_timeout_prompt")

    if cb.event_queue is None:
        return _("err.queue_uninitialized", default="[set_timer error] event_queue callback is not initialized.")

    def timer_func():
        time.sleep(seconds)
        if cb.set_status:
            cb.set_status(True, "timer_pending")
        cb.event_queue.put({"kind": "timer", "text": on_timeout_prompt or message})

    threading.Thread(target=timer_func, daemon=True).start()
    return _("out.ok", default="[set_timer] Timer set for {seconds} seconds: {message} (on_timeout_prompt={prompt})").format(
        seconds=seconds, message=message, prompt=repr(on_timeout_prompt)
    )

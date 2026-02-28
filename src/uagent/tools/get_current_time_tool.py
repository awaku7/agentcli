# tools/get_current_time.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict
import datetime

BUSY_LABEL = False  # Light tool; no Busy label needed.

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": _(
            "tool.description",
            default=(
                "Return the current time and detailed date/time information (timezone, weekday, UTC time). "
                "Use this to resolve relative date expressions (e.g., 'today', 'tomorrow', 'this weekend', "
                "'the 3rd Tuesday of next month') by determining the current weekday and UTC offset."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool provides reference information so the LLM can perform time calculations accurately.\n"
                "- ISO 8601 format (with offset)\n"
                "- Weekday (English)\n"
                "- UTC time\n"
                "- Numeric components (year, month, day, hour, minute, second)\n"
                "Use these to convert ambiguous user requests (e.g., 'next Monday') into a concrete date/time.\n"
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    # Get local time with timezone info
    now = datetime.datetime.now().astimezone()
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    # Structured output for easier parsing
    res = [
        f"ISO8601 (Local): {now.isoformat()}",
        f"ISO8601 (UTC):   {utc_now.isoformat()}",
        f"Weekday:         {now.strftime('%A')}",
        f"Timezone Name:   {now.tzname()}",
        f"UTC Offset:      {now.strftime('%z')}",
        f"Year:            {now.year}",
        f"Month:           {now.month}",
        f"Day:             {now.day}",
        f"Hour:            {now.hour}",
        f"Minute:          {now.minute}",
        f"Second:          {now.second}",
    ]

    return "[get_current_time]\n" + "\n".join(res)

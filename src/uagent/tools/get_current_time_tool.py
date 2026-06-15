from __future__ import annotations

# tools/get_current_time.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any
import datetime

BUSY_LABEL = False  # Light tool; no Busy label needed.

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": _(
            "tool.description",
            default="Return the current time and detailed date/time information (timezone, weekday, UTC time). Use this to resolve relative date expressions (e.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "current time",
                "now",
                "timezone",
                "現在時刻",
                "hora actual",
                "heure actuelle",
                "현재 시간",
                "текущее время",
            ],
        ),
        "x_search_terms_en": [
            "current time",
            "now",
            "timezone",
            "現在時刻",
            "hora actual",
            "heure actuelle",
            "현재 시간",
            "текущее время",
        ],
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
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

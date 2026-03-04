# src/uagent/tools/date_calc_tool.py
from __future__ import annotations

import datetime
import json
from typing import Any, Dict, Optional

import holidays
from dateutil.relativedelta import relativedelta

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _json_err(message: str, **extra: Any) -> str:
    obj: Dict[str, Any] = {"ok": False, "error": message}
    obj.update(extra)
    return json.dumps(obj, ensure_ascii=False)


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "date_calc",
        "description": _(
            "tool.description",
            default="Performs addition or subtraction of years, months, weeks, or days for a specified date and returns the result. Includes holiday determination using the 'holidays' library.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "base_date": {
                    "type": "string",
                    "description": _(
                        "param.base_date.description",
                        default="The base date (ISO 8601 format 'YYYY-MM-DD'. Defaults to today if omitted).",
                    ),
                },
                "years": {
                    "type": "integer",
                    "description": _(
                        "param.years.description",
                        default="Years to add (negative for subtraction).",
                    ),
                },
                "months": {
                    "type": "integer",
                    "description": _(
                        "param.months.description",
                        default="Months to add (negative for subtraction).",
                    ),
                },
                "weeks": {
                    "type": "integer",
                    "description": _(
                        "param.weeks.description",
                        default="Weeks to add (negative for subtraction).",
                    ),
                },
                "days": {
                    "type": "integer",
                    "description": _(
                        "param.days.description",
                        default="Days to add (negative for subtraction).",
                    ),
                },
                "country": {
                    "type": "string",
                    "description": _(
                        "param.country.description",
                        default="Country code for holiday determination (ISO 3166-1 alpha-2, e.g., 'JP', 'US', 'GB', 'FR'). Default is 'JP'.",
                    ),
                    "default": "JP",
                },
                "check_holiday": {
                    "type": "boolean",
                    "description": _(
                        "param.check_holiday.description",
                        default="Whether to check if the result is a holiday or weekend (default: true).",
                    ),
                    "default": True,
                },
            },
            "required": [],
        },
    },
}


def get_holiday_info(dt: datetime.datetime, country_code: str) -> Optional[str]:
    """Get the holiday name for the specified country using the holidays library."""
    try:
        if country_code.upper() == "JP":
            hols = holidays.Japan(language="ja")
        else:
            hols = holidays.country_holidays(country_code.upper())
    except Exception:
        return f"Error: Country code '{country_code}' not supported."

    # Holiday check
    holiday_name = hols.get(dt)

    # Weekend check
    weekend_name = None
    if dt.weekday() == 5:
        weekend_name = "Saturday"
    elif dt.weekday() == 6:
        weekend_name = "Sunday"

    if holiday_name and weekend_name:
        return f"Holiday ({holiday_name}) and {weekend_name}"
    if holiday_name:
        return f"Holiday ({holiday_name})"
    if weekend_name:
        return weekend_name
    return None


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    base_date_str = args.get("base_date")
    country = args.get("country", "JP")
    check_h = args.get("check_holiday", True)

    try:
        if base_date_str:
            if len(str(base_date_str)) == 10:
                base_date = datetime.datetime.strptime(str(base_date_str), "%Y-%m-%d")
            else:
                base_date = datetime.datetime.fromisoformat(str(base_date_str))
        else:
            base_date = datetime.datetime.now()
    except Exception as e:
        msg = f"[date_calc]\nError parsing base_date: {e}"
        return _json_err(msg)

    try:
        delta = relativedelta(
            years=args.get("years", 0),
            months=args.get("months", 0),
            weeks=args.get("weeks", 0),
            days=args.get("days", 0),
        )
    except Exception as e:
        return _json_err(f"[date_calc] invalid delta: {e}")

    result_date = base_date + delta

    holiday_info = get_holiday_info(result_date, str(country)) if check_h else None
    info_suffix = f" ({holiday_info})" if holiday_info else ""

    res = [
        f"Base Date:   {base_date.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Operation:   years={args.get('years', 0)}, months={args.get('months', 0)}, weeks={args.get('weeks', 0)}, days={args.get('days', 0)}",
        f"Country:     {str(country).upper()}",
        f"Result Date: {result_date.strftime('%Y-%m-%d %H:%M:%S')}{info_suffix}",
        f"ISO8601:     {result_date.isoformat()}",
        f"Weekday:     {result_date.strftime('%A')}",
    ]

    if holiday_info:
        res.append(f"Holiday Info: {holiday_info}")
    else:
        res.append("Holiday Info: Weekday")

    output = "[date_calc]\n" + "\n".join(res)

    if cb.truncate_output:
        return cb.truncate_output("date_calc", output, limit=2000)
    return output

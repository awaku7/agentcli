# src/scheck/tools/date_calc_tool.py
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

from typing import Any, Dict, Optional
import datetime
from dateutil.relativedelta import relativedelta
import holidays
from .context import get_callbacks

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "date_calc",
        "description": "指定した日付に対して年、月、週、日単位の加算・減算を行い、結果の日付を返します。世界各国の祝日判定機能（holidaysライブラリ）付き。",
        "parameters": {
            "type": "object",
            "properties": {
                "base_date": {
                    "type": "string",
                    "description": "基準となる日付 (ISO 8601形式 'YYYY-MM-DD'。省略した場合は今日)。",
                },
                "years": {
                    "type": "integer",
                    "description": "加算する年数（減算は負の数）。",
                },
                "months": {
                    "type": "integer",
                    "description": "加算する月数（減算は負の数）。",
                },
                "weeks": {
                    "type": "integer",
                    "description": "加算する週数（減算は負の数）。",
                },
                "days": {
                    "type": "integer",
                    "description": "加算する日数（減算は負の数）。",
                },
                "country": {
                    "type": "string",
                    "description": "祝日を判定する国コード (ISO 3166-1 alpha-2, 例: 'JP', 'US', 'GB', 'FR')。既定は 'JP'。",
                    "default": "JP",
                },
                "check_holiday": {
                    "type": "boolean",
                    "description": "祝日・休日かどうかを判定するかどうか（既定: true）",
                    "default": True,
                },
            },
            "required": [],
        },
    },
}


def get_holiday_info(dt: datetime.datetime, country_code: str) -> Optional[str]:
    """holidaysライブラリを使用して指定された国の祝日名を取得します。"""
    try:
        # 言語設定は日本以外はデフォルト（英語等）になる可能性がある
        if country_code.upper() == "JP":
            hols = holidays.Japan(language="ja")
        else:
            hols = holidays.country_holidays(country_code.upper())
    except Exception:
        return f"Error: Country code '{country_code}' not supported."

    # 祝日の判定
    holiday_name = hols.get(dt)

    # 週末の判定
    weekend_name = None
    if dt.weekday() == 5:
        weekend_name = "Saturday"
    elif dt.weekday() == 6:
        weekend_name = "Sunday"

    if holiday_name and weekend_name:
        return f"Holiday ({holiday_name}) and {weekend_name}"
    elif holiday_name:
        return f"Holiday ({holiday_name})"
    elif weekend_name:
        return weekend_name
    return None


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    base_date_str = args.get("base_date")
    country = args.get("country", "JP")
    check_h = args.get("check_holiday", True)

    try:
        if base_date_str:
            if len(base_date_str) == 10:
                base_date = datetime.datetime.strptime(base_date_str, "%Y-%m-%d")
            else:
                base_date = datetime.datetime.fromisoformat(base_date_str)
        else:
            base_date = datetime.datetime.now()
    except Exception as e:
        return f"[date_calc]\nError parsing base_date: {e}"

    delta = relativedelta(
        years=args.get("years", 0),
        months=args.get("months", 0),
        weeks=args.get("weeks", 0),
        days=args.get("days", 0),
    )

    result_date = base_date + delta

    holiday_info = get_holiday_info(result_date, country) if check_h else None
    info_suffix = f" ({holiday_info})" if holiday_info else ""

    res = [
        f"Base Date:   {base_date.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Operation:   years={args.get('years', 0)}, months={args.get('months', 0)}, weeks={args.get('weeks', 0)}, days={args.get('days', 0)}",
        f"Country:     {country.upper()}",
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

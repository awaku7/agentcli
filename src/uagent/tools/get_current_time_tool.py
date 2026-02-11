# tools/get_current_time.py
from typing import Any, Dict
import datetime

BUSY_LABEL = False  # 軽いので Busy 表示なしでもよい

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": (
            "現在時刻と詳細な日付情報（タイムゾーン、曜日、UTC時刻を含む）を返します。"
            "相対的な日付表現（「今日」「明日」「今週末」「来月の第3火曜日」など）を解決する際に、"
            "現在が何曜日で、どのようなオフセットを持っているかを正確に把握するために使用してください。"
        ),
        "system_prompt": """このツールは、LLMが時間計算を正確に行うための基準情報を提供します。
- ISO 8601形式（オフセット付き）
- 曜日（英語）
- UTC時刻
- 各要素（年、月、日、時、分、秒）の数値
これらを用いて、ユーザーの「来週の月曜日」といった曖昧な指定を具体的な日付に変換してください。
""",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    # タイムゾーン付きのローカル時刻を取得
    now = datetime.datetime.now().astimezone()
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    # LLMがパースしやすいように情報を構造化して出力
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

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BASE_URL = "https://nikkei225jp.com/_data/_nfsDATA/json"
ALLOWED_DATASETS = frozenset({"24", "168"})
MAX_RESPONSE_BYTES = 2_000_000
MAX_TIMEOUT = 30
MAX_POINTS = 500

_FIELD_NAMES = (
    "Bdata",
    "Max",
    "Min",
    "Ldata",
    "Per",
    "Time",
    "STtime",
    "Start",
    "End",
    "opF",
    "Pline",
    "Area",
    "Rang",
    "Keta",
)

TOOL_SPEC: dict[str, Any] = {
    "external_data": True,
    "type": "function",
    "tool_level": 1,
    "x_parallel_safe": True,
    "function": {
        "name": "nikkei225jp_chart_data",
        "description": _(
            "tool.description",
            default=(
                "Fetch chart data directly from the page's internal data endpoint at "
                "nikkei225jp.com. Returns the page-provided scalar fields and recent "
                "chart points. This is an undocumented endpoint, not an official API. "
                "code is the site's internal series ID (111 is Japan 225), not a "
                "Japanese stock ticker."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "Nikkei225jp data",
                "nikkei225jp chart data",
                "Japan 225 index",
                "Nikkei 225 AJAX",
                "世界の株価データ",
                "日経225チャートデータ",
            ],
        ),
        "x_search_terms_en": [
            "Nikkei225jp data",
            "nikkei225jp chart data",
            "Japan 225 index",
            "Nikkei 225 AJAX",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 999999,
                    "default": 111,
                    "description": _(
                        "param.code.description",
                        default=(
                            "Nikkei225jp internal chart series ID, not a stock ticker. "
                            "111 is Japan 225."
                        ),
                    ),
                },
                "dataset": {
                    "type": "string",
                    "enum": ["168", "24"],
                    "default": "168",
                    "description": _(
                        "param.dataset.description",
                        default=(
                            "Internal data-file suffix used by the website (168 or 24). "
                            "This is not an officially documented interval."
                        ),
                    ),
                },
                "max_points": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_POINTS,
                    "default": 100,
                    "description": _(
                        "param.max_points.description",
                        default=(
                            "Maximum number of latest chart points to return (1-500)."
                        ),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_TIMEOUT,
                    "default": 10,
                    "description": _(
                        "param.timeout.description",
                        default="HTTP request timeout in seconds (1-30).",
                    ),
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def _read_params(args: dict[str, Any]) -> tuple[int, str, int, int] | str:
    code = args.get("code", 111)
    dataset = args.get("dataset", "168")
    max_points = args.get("max_points", 100)
    timeout = args.get("timeout", 10)

    if isinstance(code, bool) or not isinstance(code, int) or not 1 <= code <= 999999:
        return "code must be an integer from 1 to 999999"
    if not isinstance(dataset, str) or dataset not in ALLOWED_DATASETS:
        return "dataset must be one of: 168, 24"
    if (
        isinstance(max_points, bool)
        or not isinstance(max_points, int)
        or not 1 <= max_points <= MAX_POINTS
    ):
        return f"max_points must be an integer from 1 to {MAX_POINTS}"
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or not 1 <= timeout <= MAX_TIMEOUT
    ):
        return f"timeout must be an integer from 1 to {MAX_TIMEOUT}"
    return code, dataset, max_points, timeout


def _parse_response(
    text: str, max_points: int
) -> tuple[dict[str, str], list[dict[str, int | float]]] | None:
    fields: dict[str, str] = {}
    for name in _FIELD_NAMES:
        match = re.search(
            rf"\b{re.escape(name)}\s*=\s*(\"(?:\\.|[^\"\\])*\")",
            text,
        )
        if match:
            try:
                value = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(value, str):
                fields[name] = value

    match = re.search(r"\bvar\s+Cdata\s*=\s*(\[.*?\])\s*;", text, re.DOTALL)
    if not match:
        return None
    try:
        raw_points = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw_points, list):
        return None

    points: list[dict[str, int | float]] = []
    for row in raw_points:
        if (
            not isinstance(row, list)
            or len(row) != 2
            or isinstance(row[0], bool)
            or isinstance(row[1], bool)
            or not isinstance(row[0], (int, float))
            or not isinstance(row[1], (int, float))
        ):
            continue
        points.append({"time_ms": int(row[0]), "value": float(row[1])})

    return fields, points[-max_points:]


def run_tool(args: dict[str, Any]) -> str:
    parsed = _read_params(args)
    if isinstance(parsed, str):
        return _error(parsed)
    code, dataset, max_points, timeout = parsed

    url = f"{BASE_URL}/{code}_{dataset}.json"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; uag nikkei225jp tool)",
            "Accept": "application/javascript, text/javascript, */*;q=0.8",
            "Referer": "https://nikkei225jp.com/",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            if not final_url.startswith("https://nikkei225jp.com/"):
                return _error("Unexpected redirect outside nikkei225jp.com")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            return _error("Response exceeds the 2 MB safety limit")
        text = raw.decode("utf-8-sig", errors="replace")
    except HTTPError as exc:
        return _error(f"HTTP request failed with status {exc.code}")
    except (TimeoutError, URLError, OSError) as exc:
        return _error(f"Could not fetch chart data: {exc}")

    parsed_data = _parse_response(text, max_points)
    if parsed_data is None:
        return _error(
            "The response did not match the expected chart-data format; "
            "the site's internal endpoint may have changed"
        )

    fields, points = parsed_data
    result = {
        "ok": True,
        "source": url,
        "code": code,
        "dataset": dataset,
        "fields": fields,
        "points_returned": len(points),
        "points": points,
        "note": (
            "Unofficial website-internal chart data; field meanings and update timing "
            "are not guaranteed."
        ),
    }
    return json.dumps(result, ensure_ascii=False)

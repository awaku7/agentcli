# src/uagent/tools/zipcode_check_tool.py
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BASE_URL = "https://jpzip.nadai.dev"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "external",
    "x_parallel_safe": True,
    "function": {
        "name": "zipcode_check",
        "description": _(
            "tool.description",
            default="Look up Japanese addresses by zipcode, or list cities in a prefecture. Uses the jpzip public dataset (no API key required).",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "zipcode",
                "postal code",
                "Japan address",
                "郵便番号",
                "address lookup",
                "Japanese zipcode",
                "〒",
            ],
        ),
        "x_search_terms_en": [
            "zipcode",
            "postal code",
            "Japan address",
            "address lookup",
            "Japanese zipcode",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "zipcode": {
                    "type": "string",
                    "description": _(
                        "param.zipcode.description",
                        default="7-digit Japanese zipcode to look up (e.g. '1000001'). Hyphens are ignored.",
                    ),
                },
                "prefecture": {
                    "type": "string",
                    "description": _(
                        "param.prefecture.description",
                        default="Japanese prefecture name to list cities in (e.g. '東京都', 'Kanagawa'). Kanji, kana, or romaji accepted.",
                    ),
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}

BUSY_LABEL = False
STATUS_LABEL = None


def _fetch_json(path: str) -> dict[str, Any] | None:
    """Fetch JSON from jpzip CDN."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


def _lookup_zipcode(zipcode: str) -> str:
    """Look up address by 7-digit zipcode."""
    # Normalize: remove hyphens and spaces
    z = zipcode.replace("-", "").replace(" ", "").strip()
    if not z.isdigit() or len(z) != 7:
        return json.dumps(
            {
                "ok": False,
                "error": f"Invalid zipcode format: '{zipcode}'. Must be 7 digits.",
            },
            ensure_ascii=False,
        )
    prefix3 = z[:3]
    data = _fetch_json(f"/p/{prefix3}.json")
    if data is None:
        return json.dumps(
            {"ok": False, "error": f"No data found for zipcode prefix {prefix3}."},
            ensure_ascii=False,
        )
    entry = data.get(z)
    if entry is None:
        return json.dumps(
            {"ok": False, "error": f"Zipcode {z} not found."},
            ensure_ascii=False,
        )
    # Format result
    entry.pop("prefecture_code", None)
    result = {"ok": True, "zipcode": z, "address": entry}
    return json.dumps(result, ensure_ascii=False, indent=2)


def _list_cities(prefecture: str) -> str:
    """List cities in a prefecture by scanning all prefix files."""
    # First get metadata to know prefix count
    meta = _fetch_json("/meta.json")
    if meta is None:
        return json.dumps(
            {"ok": False, "error": "Failed to fetch metadata."}, ensure_ascii=False
        )

    matched_entries: dict[str, Any] = {}
    found_pref_code = None

    for g in "0123456789":
        group_data = _fetch_json(f"/g/{g}.json")
        if group_data is None:
            continue
        for zipcode, entry in group_data.items():
            p_name = entry.get("prefecture", "")
            p_kana = entry.get("prefecture_kana", "")
            p_roma = entry.get("prefecture_roma", "")
            p_code = entry.get("prefecture_code", "")

            # Check if prefecture matches (case-insensitive for romaji)
            match = False
            if prefecture in (p_name, p_kana):
                match = True
            elif p_roma and prefecture.lower() == p_roma.lower():
                match = True
            elif prefecture in p_name or prefecture in p_kana:
                match = True

            if match:
                if found_pref_code is None:
                    found_pref_code = p_code
                if p_code == found_pref_code:
                    city_key = f"{entry.get('city', '')}|{entry.get('city_code', '')}"
                    if city_key not in matched_entries:
                        matched_entries[city_key] = {
                            "city": entry.get("city", ""),
                            "city_kana": entry.get("city_kana", ""),
                            "city_roma": entry.get("city_roma", ""),
                            "city_code": entry.get("city_code", ""),
                        }

    if not matched_entries:
        return json.dumps(
            {"ok": False, "error": f"Prefecture '{prefecture}' not found."},
            ensure_ascii=False,
        )

    cities = sorted(matched_entries.values(), key=lambda x: x.get("city_code", ""))
    # Get the actual prefecture name from first entry
    first_pref = ""
    for g in "0123456789":
        group_data = _fetch_json(f"/g/{g}.json")
        if group_data:
            for entry in group_data.values():
                if entry.get("prefecture_code") == found_pref_code:
                    first_pref = entry.get("prefecture", "")
                    break
            if first_pref:
                break

    result = {
        "ok": True,
        "prefecture": first_pref,
        "city_count": len(cities),
        "cities": cities,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def run_tool(args: dict[str, Any]) -> str:
    zipcode = args.get("zipcode", "").strip() if args.get("zipcode") else ""
    prefecture = args.get("prefecture", "").strip() if args.get("prefecture") else ""

    if zipcode and prefecture:
        return json.dumps(
            {"ok": False, "error": "Provide either zipcode or prefecture, not both."},
            ensure_ascii=False,
        )

    if zipcode:
        return _lookup_zipcode(zipcode)

    if prefecture:
        return _list_cities(prefecture)

    return json.dumps(
        {
            "ok": False,
            "error": "Provide either 'zipcode' (7 digits) or 'prefecture' (e.g. 東京都).",
            "usage": {
                "example_zipcode": {"zipcode": "1000001"},
                "example_prefecture": {"prefecture": "東京都"},
            },
        },
        ensure_ascii=False,
        indent=2,
    )

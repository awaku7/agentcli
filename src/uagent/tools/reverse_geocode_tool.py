# src/uagent/tools/reverse_geocode_tool.py
from __future__ import annotations

import json
import sys
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .context import get_callbacks
from .i18n_helper import make_tool_translator, get_locale

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "iot",
    "x_parallel_safe": False,
    "function": {
        "name": "reverse_geocode",
        "description": _(
            "tool.description",
            default="Look up an address from latitude/longitude (reverse geocoding). Uses the OpenStreetMap Nominatim API. Worldwide coverage.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "reverse geocode",
                "reverse geocoding",
                "address from coordinates",
                "lat lon to address",
                "gps to address",
                "geocode reverse",
                "location lookup",
                "address lookup",
                "coordinates to address",
            ],
        ),
        "x_search_terms_en": [
            "reverse geocode",
            "reverse geocoding",
            "address from coordinates",
            "lat lon to address",
            "gps to address",
            "geocode reverse",
            "location lookup",
            "address lookup",
            "coordinates to address",
            "geo address",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": _(
                        "param.lat.description",
                        default="Latitude (e.g. 35.6895).",
                    ),
                },
                "lon": {
                    "type": "number",
                    "description": _(
                        "param.lon.description",
                        default="Longitude (e.g. 139.6917).",
                    ),
                },
                "language": {
                    "type": "string",
                    "description": _(
                        "param.language.description",
                        default="Language for the result (ISO 639-1 code, e.g. ja, en, zh, ko). Auto-detected if omitted.",
                    ),
                },
            },
            "required": ["lat", "lon"],
        },
    },
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "agentcli/1.0"


def _lang_to_nominatim(lang: str | None) -> str:
    """Convert locale/lang code to Nominatim accept-language format."""
    if not lang:
        loc = get_locale()
        # Map internal locale codes to ISO 639-1
        if loc.startswith("ja"):
            return "ja"
        elif loc.startswith("zh_TW"):
            return "zh-TW"
        elif loc.startswith("zh"):
            return "zh"
        elif loc.startswith("ko"):
            return "ko"
        elif loc.startswith("pt_BR"):
            return "pt-BR"
        elif loc.startswith("pt"):
            return "pt"
        elif loc.startswith("hi"):
            return "hi"
        elif loc.startswith("ar"):
            return "ar"
        # For most European languages, the 2-letter code works directly
        elif len(loc) >= 2:
            return loc[:2]
        return "en"

    # Validate user-provided language
    return lang


def run_tool(args: dict[str, Any]) -> str:
    lat = args.get("lat")
    lon = args.get("lon")
    language = args.get("language")

    if lat is None or lon is None:
        return json.dumps(
            {"ok": False, "error": "Both lat and lon are required."},
            ensure_ascii=False,
        )

    cb = get_callbacks()

    # Build query parameters
    params = {
        "lat": str(lat),
        "lon": str(lon),
        "format": "json",
    }

    if language:
        params["accept-language"] = language
    else:
        params["accept-language"] = _lang_to_nominatim(None)

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{NOMINATIM_URL}?{query_string}"

    print(f"[reverse_geocode] {lat}, {lon}", file=sys.stderr)

    req = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return json.dumps(
            {
                "ok": False,
                "error": f"HTTP Error {e.code}: {e.reason}",
            },
            ensure_ascii=False,
        )
    except URLError as e:
        return json.dumps(
            {
                "ok": False,
                "error": f"URL Error: {e.reason}",
            },
            ensure_ascii=False,
        )
    except json.JSONDecodeError as e:
        return json.dumps(
            {
                "ok": False,
                "error": f"JSON decode error: {e}",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            },
            ensure_ascii=False,
        )

    if "error" in data:
        return json.dumps(
            {
                "ok": False,
                "error": data["error"],
            },
            ensure_ascii=False,
        )

    result: dict[str, Any] = {
        "ok": True,
        "display_name": data.get("display_name", ""),
        "lat": data.get("lat", str(lat)),
        "lon": data.get("lon", str(lon)),
        "address": data.get("address", {}),
        "osm_type": data.get("osm_type", ""),
        "osm_id": data.get("osm_id"),
        "licence": data.get("licence", ""),
    }

    # Use address components for a nicely formatted output
    address = result["address"]
    addr_parts: list[str] = []
    for key in ("country", "state", "city", "town", "village",
                 "suburb", "quarter", "neighbourhood", "road",
                 "house_number", "postcode"):
        val = address.get(key)
        if val:
            addr_parts.append(f"{key}: {val}")

    output_lines: list[str] = [
        "[reverse_geocode]",
        f"Coordinates: {lat}, {lon}",
        f"Language:   {params['accept-language']}",
        "",
        f"Display Name: {result['display_name']}",
        "",
        "Address Components:",
    ]
    for part in addr_parts:
        output_lines.append(f"  {part}")

    output_lines.append("")
    output_lines.append(f"OSM: {result.get('osm_type', '')}/{result.get('osm_id', '')}")
    output_lines.append(f"Licence: {result.get('licence', '')}")

    output = "\n".join(output_lines)

    if cb.truncate_output:
        return cb.truncate_output("reverse_geocode", output, limit=2000)
    return output

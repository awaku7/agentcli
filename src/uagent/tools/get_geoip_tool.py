# tools/get_geoip_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
from typing import Any, Dict

from .fetch_url_tool import run_tool as fetch_url_run

BUSY_LABEL = True
STATUS_LABEL = "tool:get_geoip"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_geoip",
        "description": _(
            "tool.description",
            default=(
                "Estimate the user's rough location based on their public IP address. "
                "The result may be inaccurate when using VPN/proxies/mobile networks.\n\n"
                "Policy:\n"
                "- Use this tool when you need the user's approximate location (city/region/country) and the user has not provided it.\n"
                "- If the user already provided their location, prefer that and do not call get_geoip."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Fetch IP-based location data from an external service (ipinfo.io) and return a simplified result."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": _(
                        "param.format.description",
                        default="Output format: 'text' or 'json' (default: 'text').",
                    ),
                    "enum": ["text", "json"],
                }
            },
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    out_format = str((args or {}).get("format") or "text").strip().lower()
    if out_format not in ("text", "json"):
        return "[get_geoip error] format must be 'text' or 'json'"

    # Note: Consent handling has been removed. The deprecated 'require_consent'
    # parameter is not supported and is intentionally absent from the schema.

    raw = fetch_url_run({"url": "https://ipinfo.io/json"})

    # Strip fetch_url metadata line(s) and extract JSON payload.
    idx = raw.find("\n{")
    json_text = raw[idx + 1 :] if idx >= 0 else raw

    try:
        data = json.loads(json_text)
    except Exception as e:
        return (
            "[get_geoip error] failed to parse ipinfo.io response as JSON: "
            + repr(e)
            + "\n\n"
            + raw
        )

    result = {
        "ip": data.get("ip"),
        "city": data.get("city"),
        "region": data.get("region"),
        "country": data.get("country"),
        "loc": data.get("loc"),
        "org": data.get("org"),
        "postal": data.get("postal"),
        "timezone": data.get("timezone"),
    }

    if out_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    lines = [
        "[get_geoip] IP-based location estimate (via ipinfo.io)",
        f"IP: {result.get('ip')}",
        f"Country: {result.get('country')}",
        f"Region: {result.get('region')}",
        f"City: {result.get('city')}",
        f"Coordinates (approx): {result.get('loc')}",
        f"Timezone: {result.get('timezone')}",
        f"Org: {result.get('org')}",
        "Note: Results may be inaccurate when using VPN/proxies/mobile networks.",
    ]
    return "\n".join(lines)

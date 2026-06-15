# tools/get_geoip_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
from typing import Any

from .fetch_url_tool import run_tool as fetch_url_run

BUSY_LABEL = True
STATUS_LABEL = "tool:get_geoip"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,
    "type": "function",
    "function": {
        "name": "get_geoip",
        "description": _(
            "tool.description",
            default="Estimate the user's rough location based on their public IP address. The result may be inaccurate when using VPN/proxies/mobile networks.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Fetch IP-based location data from an external service (ipinfo.io) and return a simplified result."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "get_geoip",
                "get geoip",
                "location",
                "country",
                "ip geolocation",
                "geo ip",
            ],
        ),
        "x_search_terms_en": [
            "get_geoip",
            "get geoip",
            "location",
            "country",
            "ip geolocation",
            "geo ip",
        ],
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


def run_tool(args: dict[str, Any]) -> str:
    out_format = str((args or {}).get("format") or "text").strip().lower()
    if out_format not in ("text", "json"):
        return _(
            "err.format_invalid",
            default="[get_geoip error] format must be 'text' or 'json'",
        )

    # Note: Consent handling has been removed. The deprecated 'require_consent'
    # parameter is not supported and is intentionally absent from the schema.

    # Note: verify_ssl is disabled by default because corporate SSL-inspection
    # proxies (e.g. Zscaler) often break certificate verification, and this
    # tool only fetches non-sensitive, approximate location data.
    raw = fetch_url_run({"url": "https://ipinfo.io/json", "verify_ssl": False})
    if isinstance(raw, str) and '"ok": false' in raw and "SSL error:" in raw:
        return raw

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

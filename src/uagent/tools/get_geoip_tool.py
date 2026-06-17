# tools/get_geoip_tool.py
#
# IP geolocation tool with optional local DB support (DB-IP Lite, CC-BY 4.0).
# When UAGENT_GEOIP_DB_PATH points to a .mmdb file and maxminddb is installed,
# lookups are performed entirely offline. Otherwise, falls back to ipinfo.io API.

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
import os
from typing import Any

from ..env_utils import env_get
from .fetch_url_tool import run_tool as fetch_url_run

BUSY_LABEL = True
STATUS_LABEL = "tool:get_geoip"

# --- Optional local DB support -------------------------------------------
# maxminddb is an optional dependency. If not installed or no DB path is
# configured, the tool falls back to the ipinfo.io API.

_mmdb_reader = None  # type: Any
_mmdb_checked = False


def _get_mmdb_reader() -> Any:
    """Return a cached maxminddb.Reader, or None if unavailable."""
    global _mmdb_reader, _mmdb_checked
    if _mmdb_checked:
        return _mmdb_reader
    _mmdb_checked = True

    db_path = env_get("UAGENT_GEOIP_DB_PATH") or ""
    if not db_path:
        # Fall back to bundled DB-IP Lite database (src/uagent/data/).
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "dbip-city-lite.mmdb",
        )
    if not db_path or not os.path.isfile(db_path):
        return None

    try:
        import maxminddb  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:
        _mmdb_reader = maxminddb.open_database(db_path)
    except Exception:
        _mmdb_reader = None
    return _mmdb_reader


# --- Tool spec -----------------------------------------------------------

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "get_geoip",
        "description": _(
            "tool.description",
            default="Estimate the user's rough location based on their public IP address. The result may be inaccurate when using VPN/proxies/mobile networks.",
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
                },
                "ip": {
                    "type": "string",
                    "description": _(
                        "param.ip.description",
                        default="Optional IP address to look up. If omitted, the current public IP is used (API mode only).",
                    ),
                },
            },
            "required": [],
        },
    },
}


# --- Local DB lookup -----------------------------------------------------


def _lookup_local(ip: str) -> dict[str, Any] | None:
    """Look up *ip* in the local mmdb database. Returns None on failure."""
    reader = _get_mmdb_reader()
    if reader is None:
        return None
    try:
        rec = reader.get(ip)
    except Exception:
        return None
    if not rec:
        return None

    # DB-IP Lite mmdb uses MaxMind-style nested records:
    #   country: {"iso_code": "US", "names": {"en": "United States", ...}}
    #   city: {"names": {"en": "Mountain View", ...}}
    #   subdivisions: [{"names": {"en": "California", ...}}]
    #   location: {"latitude": 37.4, "longitude": -122.0}
    country_info = rec.get("country") or {}
    country_names = country_info.get("names") or {}
    city_info = rec.get("city") or {}
    city_names = city_info.get("names") or {}
    location = rec.get("location") or {}
    subdivisions = rec.get("subdivisions") or []

    lat = location.get("latitude")
    lon = location.get("longitude")
    loc_str = f"{lat},{lon}" if lat is not None and lon is not None else None

    region_name = None
    if subdivisions:
        region_name = (subdivisions[0].get("names") or {}).get("en")

    return {
        "ip": ip,
        "city": city_names.get("en"),
        "region": region_name,
        "country": country_info.get("iso_code"),
        "country_name": country_names.get("en"),
        "loc": loc_str,
        "org": rec.get("isp") or rec.get("organization"),
        "postal": rec.get("postal_code") or rec.get("zip_code"),
        "timezone": location.get("time_zone"),
        "source": "db-ip-lite (local)",
    }


# --- API lookup (fallback) -----------------------------------------------


def _lookup_api() -> dict[str, Any] | str:
    """Fetch geolocation from ipinfo.io. Returns dict on success, str error."""
    # Note: verify_ssl is disabled by default because corporate SSL-inspection
    # proxies (e.g. Zscaler) often break certificate verification, and this
    # tool only fetches non-sensitive, approximate location data.
    raw = fetch_url_run({"url": "https://ipinfo.io/json", "ssl": False})
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

    return {
        "ip": data.get("ip"),
        "city": data.get("city"),
        "region": data.get("region"),
        "country": data.get("country"),
        "loc": data.get("loc"),
        "org": data.get("org"),
        "postal": data.get("postal"),
        "timezone": data.get("timezone"),
        "source": "ipinfo.io (API)",
    }


# --- Main entry point ----------------------------------------------------


def run_tool(args: dict[str, Any]) -> str:
    out_format = str((args or {}).get("format") or "text").strip().lower()
    if out_format not in ("text", "json"):
        return _(
            "err.format_invalid",
            default="[get_geoip error] format must be 'text' or 'json'",
        )

    target_ip = str((args or {}).get("ip") or "").strip() or None

    # Try local DB first (works for any IP, fully offline).
    if target_ip:
        result = _lookup_local(target_ip)
        if result is None:
            return _(
                "err.local_db_unavailable",
                default=(
                    "[get_geoip error] Local DB not configured. "
                    "Set UAGENT_GEOIP_DB_PATH to a .mmdb file and install "
                    "maxminddb to look up arbitrary IP addresses offline."
                ),
            )
    else:
        # No specific IP: try local DB with current public IP via API first,
        # then local lookup. If local DB is available, we still need the
        # public IP from somewhere — try a lightweight API call.
        reader = _get_mmdb_reader()
        if reader is not None:
            # Get public IP from a minimal API, then look up locally.
            ip_raw = fetch_url_run(
                {"url": "https://api.ipify.org?format=text", "ssl": False}
            )
            # Extract IP from response (strip metadata lines).
            if isinstance(ip_raw, str):
                for line in ip_raw.strip().splitlines():
                    line = line.strip()
                    if line and not line.startswith("[") and not line.startswith("{"):
                        target_ip = line
                        break
            if target_ip:
                result = _lookup_local(target_ip)
                if result is None:
                    # DB lookup failed for the public IP; fall back to API.
                    result = _lookup_api()
                    if isinstance(result, str):
                        return result
            else:
                # Could not determine public IP; fall back to API.
                result = _lookup_api()
                if isinstance(result, str):
                    return result
        else:
            # No local DB; use API directly.
            result = _lookup_api()
            if isinstance(result, str):
                return result

    if out_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    source = result.get("source", "unknown")
    lines = [
        f"[get_geoip] IP-based location estimate (via {source})",
        f"IP: {result.get('ip')}",
        f"Country: {result.get('country')}",
    ]
    if result.get("country_name"):
        lines.append(f"Country name: {result.get('country_name')}")
    lines.append(f"Region: {result.get('region')}")
    lines.append(f"City: {result.get('city')}")
    lines.append(f"Coordinates (approx): {result.get('loc')}")
    lines.append(f"Timezone: {result.get('timezone')}")
    lines.append(f"Org: {result.get('org')}")
    lines.append(
        "Note: Results may be inaccurate when using VPN/proxies/mobile networks."
    )
    return "\n".join(lines)

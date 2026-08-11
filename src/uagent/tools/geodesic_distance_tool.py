"""Calculate straight-line distance between two geographic coordinates."""

from __future__ import annotations

import json
import math
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "utility",
    "x_parallel_safe": True,
    "function": {
        "name": "geodesic_distance",
        "description": _(
            "tool.description",
            default=(
                "Calculate the straight-line distance between two latitude/longitude "
                "points using the Haversine formula. Optionally resolves both points "
                "to addresses with OpenStreetMap Nominatim."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "straight-line distance",
                "geodesic distance",
                "distance between coordinates",
                "haversine distance",
                "latitude longitude distance",
                "緯度経度の距離",
                "直線距離",
            ],
        ),
        "x_search_terms_en": [
            "straight-line distance",
            "geodesic distance",
            "distance between coordinates",
            "haversine distance",
            "latitude longitude distance",
            "緯度経度の距離",
            "直線距離",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "lat_a": {
                    "type": "number",
                    "description": _(
                        "param.lat_a.description", default="Latitude of point A."
                    ),
                },
                "lon_a": {
                    "type": "number",
                    "description": _(
                        "param.lon_a.description", default="Longitude of point A."
                    ),
                },
                "lat_b": {
                    "type": "number",
                    "description": _(
                        "param.lat_b.description", default="Latitude of point B."
                    ),
                },
                "lon_b": {
                    "type": "number",
                    "description": _(
                        "param.lon_b.description", default="Longitude of point B."
                    ),
                },
                "resolve_addresses": {
                    "type": "boolean",
                    "description": _(
                        "param.resolve_addresses.description",
                        default="Also resolve both coordinates to addresses.",
                    ),
                    "default": False,
                },
                "language": {
                    "type": "string",
                    "description": _(
                        "param.language.description",
                        default="Address language for optional reverse geocoding.",
                    ),
                },
            },
            "required": ["lat_a", "lon_a", "lat_b", "lon_b"],
        },
    },
}

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


def _coordinate(value: Any, name: str, low: float, high: float) -> float:
    result = float(value)
    if not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return result


def _reverse(lat: float, lon: float, language: str) -> str | None:
    params = urlencode(
        {"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1}
    )
    request = Request(
        f"{_NOMINATIM_URL}?{params}",
        headers={"User-Agent": "agentcli/1.0 (geodesic_distance)"},
    )
    if language:
        request.add_header("Accept-Language", language)
    with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed HTTPS endpoint
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("display_name") if isinstance(payload, dict) else None


def run_tool(args: dict[str, Any]) -> str:
    try:
        lat_a = _coordinate(args.get("lat_a"), "lat_a", -90, 90)
        lon_a = _coordinate(args.get("lon_a"), "lon_a", -180, 180)
        lat_b = _coordinate(args.get("lat_b"), "lat_b", -90, 90)
        lon_b = _coordinate(args.get("lon_b"), "lon_b", -180, 180)
        phi1, phi2 = math.radians(lat_a), math.radians(lat_b)
        dphi = math.radians(lat_b - lat_a)
        dlambda = math.radians(lon_b - lon_a)
        hav = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        distance_km = 6371.0088 * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))
        bearing = (
            math.degrees(
                math.atan2(
                    math.sin(dlambda) * math.cos(phi2),
                    math.cos(phi1) * math.sin(phi2)
                    - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda),
                )
            )
            + 360
        ) % 360
        output: dict[str, Any] = {
            "ok": True,
            "point_a": {"lat": lat_a, "lon": lon_a},
            "point_b": {"lat": lat_b, "lon": lon_b},
            "distance_km": round(distance_km, 6),
            "distance_m": round(distance_km * 1000, 3),
            "initial_bearing_degrees": round(bearing, 3),
            "method": "Haversine",
        }
        if args.get("resolve_addresses"):
            language = str(args.get("language") or "")
            output["address_a"] = _reverse(lat_a, lon_a, language)
            output["address_b"] = _reverse(lat_b, lon_b, language)
        text = json.dumps(output, ensure_ascii=False)
        callbacks = get_callbacks()
        return (
            callbacks.truncate_output("geodesic_distance", text, limit=4000)
            if callbacks.truncate_output
            else text
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


__all__ = ["TOOL_SPEC", "run_tool"]

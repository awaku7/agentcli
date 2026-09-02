"""Search public-transit routes through a selected route provider."""

from __future__ import annotations

import datetime as _dt
import html as _html
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ..lazy_import import lazy_module

requests = lazy_module("requests")

from ..auth.provider_credentials import get_provider_api_key
from .arg_util import get_int, get_list, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "web",
    "x_parallel_safe": True,
    "function": {
        "name": "public_transit_route",
        "description": _(
            "tool.description",
            default=(
                "Search Japanese public-transit routes with a selected provider (Yahoo! Japan Transit or Google Maps). "
                "Returns multiple candidate routes, total fare, per-operator or per-segment fare breakdown, travel time, transfers, and itinerary."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "public transit",
                "train route",
                "route search",
                "transfer guide",
                "train fare",
                "乗換案内",
                "電車",
                "鉄道運賃",
                "バス経路",
                "Yahoo transit",
            ],
        ),
        "x_search_terms_en": [
            "public transit",
            "train route",
            "route search",
            "transfer guide",
            "train fare",
            "乗換案内",
            "電車",
            "鉄道運賃",
            "バス経路",
            "Yahoo transit",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": _(
                        "param.origin.description",
                        default="Departure station, bus stop, address, or facility.",
                    ),
                },
                "destination": {
                    "type": "string",
                    "description": _(
                        "param.destination.description",
                        default="Arrival station, bus stop, address, or facility.",
                    ),
                },
                "provider": {
                    "type": "string",
                    "description": _(
                        "param.provider.description",
                        default="Route provider: yahoo or google.",
                    ),
                    "enum": ["yahoo", "google"],
                    "default": "yahoo",
                },
                "departure": {
                    "type": "string",
                    "description": _(
                        "param.departure.description",
                        default=(
                            "Optional local departure date/time in ISO 8601 format. "
                            "Defaults to the current local time."
                        ),
                    ),
                },
                "max_routes": {
                    "type": "integer",
                    "description": _(
                        "param.max_routes.description",
                        default="Maximum number of candidate routes to return (1-6, default: 3).",
                    ),
                    "default": 3,
                    "minimum": 1,
                    "maximum": 6,
                },
                "sort_by": {
                    "type": "string",
                    "description": _(
                        "param.sort_by.description",
                        default=(
                            "Route order: recommended/fastest, cheapest, or fewest_transfers."
                        ),
                    ),
                    "enum": ["recommended", "fastest", "cheapest", "fewest_transfers"],
                    "default": "recommended",
                },
                "ticket": {
                    "type": "string",
                    "description": _(
                        "param.ticket.description",
                        default="Fare preference: ic (default) or normal ticket.",
                    ),
                    "enum": ["ic", "normal"],
                    "default": "ic",
                },
                "avoid": {
                    "type": "array",
                    "description": _(
                        "param.avoid.description",
                        default=(
                            "Transport types to avoid: shinkansen, limited_express, airline, "
                            "highway_bus, local_bus, or ship."
                        ),
                    ),
                    "items": {"type": "string"},
                },
            },
            "required": ["origin", "destination"],
        },
    },
}

_BASE_URL = "https://transit.yahoo.co.jp/search/result"
_SORT_VALUES = {
    "recommended": "0",
    "fastest": "0",
    "cheapest": "1",
    "fewest_transfers": "2",
}
_AVOID_KEYS = {
    "shinkansen": "shin",
    "limited_express": "ex",
    "airline": "al",
    "highway_bus": "hb",
    "local_bus": "lb",
    "ship": "sr",
}
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


_STATION_MASTER = Path(__file__).resolve().parent / "data" / "jp_stations.json"
_STATIONS: list[dict[str, Any]] | None = None


def _normalize_station_name(value: str) -> str:
    return re.sub(r"駅$", "", value.strip().replace("（", "(").replace("）", ")"))


def _load_stations() -> list[dict[str, Any]]:
    global _STATIONS
    if _STATIONS is None:
        try:
            raw = json.loads(_STATION_MASTER.read_text(encoding="utf-8"))
            _STATIONS = [item for item in raw if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            _STATIONS = []
    return _STATIONS


def _station_candidates(name: str) -> list[dict[str, Any]]:
    normalized = _normalize_station_name(name)
    return [
        station
        for station in _load_stations()
        if _normalize_station_name(str(station.get("name", ""))) == normalized
        and isinstance(station.get("lat"), (int, float))
        and isinstance(station.get("lng"), (int, float))
    ]


def _distance_km(first: dict[str, Any], second: dict[str, Any]) -> float:
    lat1, lon1 = math.radians(float(first["lat"])), math.radians(float(first["lng"]))
    lat2, lon2 = math.radians(float(second["lat"])), math.radians(float(second["lng"]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def _resolve_origin(origin: str, destination: str) -> str:
    """Prefer the same-name origin station geographically nearest the destination."""
    origins = _station_candidates(origin)
    destinations = _station_candidates(destination)
    if len(origins) < 2 or not destinations:
        return origin
    selected = min(
        origins,
        key=lambda candidate: min(
            _distance_km(candidate, target) for target in destinations
        ),
    )
    name = str(selected.get("name", origin))
    if _normalize_station_name(name) == "郡山":
        return "郡山(奈良県)" if float(selected["lat"]) < 35.0 else "郡山(福島県)"
    return name


def _error(message: str, **extra: Any) -> str:
    value: dict[str, Any] = {"ok": False, "error": message}
    value.update(extra)
    return json.dumps(value, ensure_ascii=False)


def _parse_departure(value: str) -> _dt.datetime:
    if not value:
        return _dt.datetime.now().replace(second=0, microsecond=0)
    raw = value.strip().replace("Z", "+00:00")
    parsed = _dt.datetime.fromisoformat(raw)
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed.replace(second=0, microsecond=0)


def _build_params(args: dict[str, Any]) -> dict[str, str]:
    departure = _parse_departure(get_str(args, "departure", ""))
    avoid = {str(v).strip().lower() for v in get_list(args, "avoid") if str(v).strip()}
    params = {
        "from": get_str(args, "origin", "").strip(),
        "to": get_str(args, "destination", "").strip(),
        "fromgid": "",
        "togid": "",
        "flatlon": "",
        "tlatlon": "",
        "via": "",
        "viacode": "",
        "y": f"{departure.year:04d}",
        "m": f"{departure.month:02d}",
        "d": f"{departure.day:02d}",
        "hh": f"{departure.hour:02d}",
        "m1": str(departure.minute // 10),
        "m2": str(departure.minute % 10),
        "type": "1",
        "ticket": get_str(args, "ticket", "ic").strip().lower() or "ic",
        "expkind": "1",
        "userpass": "1",
        "ws": "3",
        "s": _SORT_VALUES.get(
            get_str(args, "sort_by", "recommended").strip().lower(), "0"
        ),
        "al": "0" if "airline" in avoid else "1",
        "shin": "0" if "shinkansen" in avoid else "1",
        "ex": "0" if "limited_express" in avoid else "1",
        "hb": "0" if "highway_bus" in avoid else "1",
        "lb": "0" if "local_bus" in avoid else "1",
        "sr": "0" if "ship" in avoid else "1",
    }
    return params


def _parse_next_data(text: str) -> dict[str, Any]:
    match = _NEXT_DATA_RE.search(text)
    if not match:
        raise ValueError("Yahoo! Transit result data was not found")
    raw = _html.unescape(match.group(1))
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Yahoo! Transit returned invalid result data")
    return data


def _fare_breakdown(edges: list[Any]) -> list[dict[str, Any]]:
    """Split Yahoo fares into payable units such as JR and Osaka Metro."""
    base_by_group: dict[str, dict[str, Any]] = {}
    extra_by_group: dict[str, dict[str, Any]] = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        price = edge.get("priceInfo") or {}
        if not isinstance(price, dict):
            continue
        group = str(price.get("edgeGroup") or f"edge-{index}")
        operator = _operator_name(str(edge.get("railName") or "").strip())
        base = _to_int(price.get("price")) or 0
        extra = _to_int(price.get("expPrice")) or 0
        if base > 0 and group not in base_by_group:
            base_by_group[group] = {
                "amount_yen": base,
                "operator": operator,
                "from_station": str(edge.get("stationName") or ""),
                "to_station": str(edge.get("destination") or ""),
            }
        if extra > 0:
            extra_by_group[group] = {
                "amount_yen": max(
                    extra_by_group.get(group, {}).get("amount_yen", 0), extra
                ),
                "operator": operator,
                "from_station": str(edge.get("stationName") or ""),
                "to_station": str(edge.get("destination") or ""),
            }
    breakdown: list[dict[str, Any]] = []
    for group, item in base_by_group.items():
        breakdown.append(
            {
                "unit": "fare",
                "label": _("fare.ticket", default="Fare"),
                **item,
            }
        )
        extra = extra_by_group.get(group)
        if extra:
            breakdown.append(
                {
                    "unit": "surcharge",
                    "label": _("fare.surcharge", default="Surcharge"),
                    "amount_yen": extra["amount_yen"],
                    "operator": extra["operator"],
                }
            )
    return breakdown


def _operator_name(rail_name: str) -> str:
    if "OsakaMetro" in rail_name or "大阪メトロ" in rail_name:
        return "OsakaMetro"
    if "ＪＲ" in rail_name or "JR" in rail_name:
        return "JR"
    if "近鉄" in rail_name:
        return "近鉄"
    if "阪急" in rail_name:
        return "阪急"
    if "阪神" in rail_name:
        return "阪神"
    if "南海" in rail_name:
        return "南海"
    return rail_name.split("・", 1)[0] if rail_name else "交通機関"


def _route_from_feature(
    feature: dict[str, Any], rank: int, payment_unit: str = "ic"
) -> dict[str, Any]:
    summary = feature.get("summaryInfo") or {}
    edges = feature.get("edgeInfoList") or []
    segments: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        rail = str(edge.get("railName") or "").strip()
        station = str(edge.get("stationName") or "").strip()
        if not rail or rail == "徒歩":
            continue
        key = (rail, station, str(edge.get("destination") or ""))
        if key in seen:
            continue
        seen.add(key)
        segments.append(
            {
                "station": station,
                "line": rail,
                "destination": edge.get("destination"),
                "departure": (edge.get("timeInfo") or [{}])[0].get("time"),
            }
        )
    return {
        "rank": rank,
        "departure": summary.get("departureTime"),
        "arrival": summary.get("arrivalTime"),
        "duration": summary.get("totalTime"),
        "duration_minutes": _duration_minutes(summary.get("totalTime")),
        "transfers": _to_int(summary.get("transferCount")),
        "fare_yen": _to_int(summary.get("totalPrice")),
        "fare_detail": summary.get("totalPriceDetail"),
        "payment_unit": payment_unit,
        "fare_breakdown": _fare_breakdown(edges),
        "distance_km": summary.get("distance"),
        "segments": segments,
        "itinerary": (summary.get("calendarData") or {}).get("description", ""),
        "is_fastest": bool(summary.get("isFast")),
        "is_easiest": bool(summary.get("isEasy")),
        "is_cheapest": bool(summary.get("isCheap")),
    }


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", "").replace("円", "").strip())
    except (TypeError, ValueError):
        return None


def _duration_minutes(value: Any) -> int | None:
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("text") or value.get("duration") or value.get("seconds")
    if isinstance(value, (int, float)):
        return round(float(value) / 60)
    text = str(value)
    match = re.search(
        r"(?:(\d+)\s*(?:時間|hours?|hrs?))?\s*" r"(?:(\d+)\s*(?:分|minutes?|mins?))?",
        text,
        re.IGNORECASE,
    )
    if not match or (match.group(1) is None and match.group(2) is None):
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


_GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def _google_route(route: dict[str, Any], rank: int) -> dict[str, Any]:
    legs = route.get("legs") or []
    leg = (
        legs[0] if isinstance(legs, list) and legs and isinstance(legs[0], dict) else {}
    )
    segments: list[dict[str, Any]] = []
    for step in leg.get("steps") or []:
        if not isinstance(step, dict):
            continue
        transit = step.get("transitDetails") or step.get("transit_details") or {}
        line = transit.get("transitLine") or transit.get("line") or {}
        vehicle = line.get("vehicle") or {}
        stop_details = transit.get("stopDetails") or {
            "departureStop": transit.get("departure_stop") or {},
            "arrivalStop": transit.get("arrival_stop") or {},
        }
        if transit:
            departure_stop = stop_details.get("departureStop") or {}
            arrival_stop = stop_details.get("arrivalStop") or {}
            agencies = line.get("agencies") or []
            segments.append(
                {
                    "station": departure_stop.get("name"),
                    "arrival_station": arrival_stop.get("name"),
                    "line": line.get("nameShort")
                    or line.get("short_name")
                    or line.get("name"),
                    "operator": (agencies[0] if agencies else {}).get("name"),
                    "vehicle": vehicle.get("name") or vehicle.get("type"),
                    "departure": (step.get("localizedValues") or {}).get(
                        "departureTime"
                    ),
                    "arrival": (step.get("localizedValues") or {}).get("arrivalTime"),
                    "duration_minutes": _duration_minutes(
                        step.get("localizedValues", {}).get("staticDuration")
                    ),
                }
            )
        elif step.get("travelMode") == "WALK":
            segments.append(
                {
                    "line": _("segment.walk", default="Walking"),
                    "vehicle": "WALK",
                    "duration_minutes": _duration_minutes(
                        step.get("localizedValues", {}).get("staticDuration")
                    ),
                }
            )
    return {
        "rank": rank,
        "departure": (leg.get("localizedValues") or {}).get("startTime"),
        "arrival": (leg.get("localizedValues") or {}).get("endTime"),
        "duration": (
            route.get("localizedValues", {}).get("duration")
            or leg.get("localizedValues", {}).get("duration")
            or (leg.get("duration") or {}).get("text")
            or leg.get("duration")
        ),
        "duration_minutes": _duration_minutes(
            route.get("localizedValues", {}).get("duration")
            or leg.get("localizedValues", {}).get("duration")
            or (leg.get("duration") or {}).get("text")
            or leg.get("duration")
        ),
        "transfers": max(
            0, sum(1 for segment in segments if segment.get("arrival_station")) - 1
        ),
        "fare_amount": _to_int(
            (route.get("travelAdvisory") or {}).get("transitFare", {}).get("units")
        ),
        "fare_yen": (
            _to_int(
                (route.get("travelAdvisory") or {}).get("transitFare", {}).get("units")
            )
            if ((route.get("travelAdvisory") or {}).get("transitFare") or {}).get(
                "currencyCode"
            )
            == "JPY"
            else None
        ),
        "fare_currency": (
            (route.get("travelAdvisory") or {}).get("transitFare") or {}
        ).get("currencyCode"),
        "fare_detail": None,
        "payment_unit": "google",
        "fare_breakdown": [],
        "distance_km": round(float(route.get("distanceMeters", 0) or 0) / 1000, 3),
        "segments": segments,
        "itinerary": route.get("description") or "",
        "is_fastest": rank == 1,
        "is_easiest": False,
        "is_cheapest": False,
    }


def _google_waypoint(value: str) -> dict[str, Any]:
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", value)
    if match:
        return {
            "location": {
                "latLng": {
                    "latitude": float(match.group(1)),
                    "longitude": float(match.group(2)),
                }
            }
        }
    return {"address": value}


def _run_google(
    args: dict[str, Any], origin: str, destination: str, max_routes: int
) -> str:
    api_key = (get_provider_api_key("google_maps") or "").strip()
    if not api_key:
        return _error(
            _(
                "err.google_key_missing",
                default="UAGENT_GOOGLE_MAPS_API_KEY is not set.",
            ),
            provider="google",
        )
    departure_raw = get_str(args, "departure", "").strip()
    payload = {
        "origin": _google_waypoint(origin),
        "destination": _google_waypoint(destination),
        "travelMode": "TRANSIT",
        "languageCode": "ja",
        "units": "METRIC",
        # Match Google's official transit example. Routes API may return up
        # to three alternatives when available.
        "computeAlternativeRoutes": True,
        "transitPreferences": {
            "allowedTravelModes": ["TRAIN"],
            "routingPreference": "FEWER_TRANSFERS",
        },
    }
    if departure_raw:
        departure = _parse_departure(departure_raw)
        payload["departureTime"] = departure.astimezone().isoformat(timespec="seconds")
    # If omitted, Routes API uses the current time in the routing service.
    # The official transit example uses routes.*; it also avoids field-mask
    # spelling differences between REST and protobuf JSON names.
    field_mask = "routes.*"
    response = requests.post(
        _GOOGLE_ROUTES_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    raw_routes = data.get("routes") or []
    routes = [
        _google_route(route, index)
        for index, route in enumerate(raw_routes[:max_routes], 1)
    ]
    if not routes:
        return _error(
            _("err.no_routes", default="No public-transit routes were found."),
            origin=origin,
            destination=destination,
            provider="google",
            source="Google Routes API",
        )
    return json.dumps(
        {
            "ok": True,
            "origin": origin,
            "destination": destination,
            "routes": routes,
            "provider": "google",
            "source": "Google Routes API",
            "source_url": _GOOGLE_ROUTES_URL,
            "checked_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "fare_type": "provider_dependent",
            "notice": _(
                "notice.google_fare",
                default="Google route availability and fares are provider-dependent and may change.",
            ),
        },
        ensure_ascii=False,
    )


def run_tool(args: dict[str, Any]) -> str:
    """Query Yahoo! Japan Transit and return normalized candidate routes."""
    origin = get_str(args, "origin", "").strip()
    destination = get_str(args, "destination", "").strip()
    if not origin or not destination:
        return _error(
            _(
                "err.locations_missing",
                default="Both origin and destination are required.",
            )
        )
    provider = get_str(args, "provider", "yahoo").strip().lower() or "yahoo"
    if provider not in {"yahoo", "google"}:
        return _error(
            _(
                "err.provider_invalid",
                default="Provider must be either yahoo or google.",
            ),
            provider=provider,
        )
    max_routes = max(1, min(6, get_int(args, "max_routes", 3)))
    if provider == "google":
        try:
            return _run_google(args, origin, destination, max_routes)
        except Exception as exc:
            return _error(
                _(
                    "err.google_search_failed",
                    default="Google Maps route search failed: %(error)s",
                )
                % {"error": str(exc)},
                origin=origin,
                destination=destination,
                provider="google",
                source="Google Routes API",
            )
    resolved_origin = _resolve_origin(origin, destination)
    search_args = dict(args)
    search_args["origin"] = resolved_origin
    params = _build_params(search_args)
    try:
        response = requests.get(
            _BASE_URL,
            params=params,
            headers={"User-Agent": "Mozilla/5.0 (compatible; uagent transit tool)"},
            timeout=20,
        )
        response.raise_for_status()
        data = _parse_next_data(response.text)
        page = (data.get("props") or {}).get("pageProps") or {}
        navi = page.get("naviSearchParam") or {}
        features = navi.get("featureInfoList") or []
        if not isinstance(features, list) or not features:
            return _error(
                _(
                    "err.no_routes",
                    default="No public-transit routes were found.",
                ),
                origin=origin,
                destination=destination,
                source="Yahoo! Japan Transit",
            )
        all_features = [feature for feature in features if isinstance(feature, dict)]
        if max_routes > len(all_features):
            # Yahoo! displays three routes per result page. Fetch the next page
            # only when the caller explicitly asks for more candidates.
            page_params = dict(params)
            page_params.update({"fl": "4", "tl": str(max_routes)})
            next_response = requests.get(
                _BASE_URL,
                params=page_params,
                headers={"User-Agent": "Mozilla/5.0 (compatible; uagent transit tool)"},
                timeout=20,
            )
            next_response.raise_for_status()
            next_data = _parse_next_data(next_response.text)
            next_page = (next_data.get("props") or {}).get("pageProps") or {}
            next_navi = next_page.get("naviSearchParam") or {}
            next_features = next_navi.get("featureInfoList") or []
            if isinstance(next_features, list):
                all_features.extend(
                    feature for feature in next_features if isinstance(feature, dict)
                )
        routes = [
            _route_from_feature(feature, index, params["ticket"])
            for index, feature in enumerate(all_features[:max_routes], 1)
        ]
        query = urlencode(params, doseq=True)
        output = {
            "ok": True,
            "origin": origin,
            "origin_resolved": resolved_origin,
            "destination": destination,
            "routes": routes,
            "provider": "yahoo",
            "source": "Yahoo! Japan Transit",
            "source_url": f"{_BASE_URL}?{query}",
            "source_link": _(
                "source.link",
                default="[Open Yahoo! Japan Transit route search](%(url)s)",
            )
            % {"url": f"{_BASE_URL}?{query}"},
            "checked_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "fare_type": "web_checked",
            "notice": _(
                "notice.fare",
                default="Fares and schedules are provided by Yahoo! Japan Transit and may change.",
            ),
        }
        cb = get_callbacks()
        text = json.dumps(output, ensure_ascii=False)
        if cb.truncate_output:
            return cb.truncate_output("public_transit_route", text, limit=12000)
        return text
    except Exception as exc:
        return _error(
            _(
                "err.search_failed",
                default="Yahoo! Japan Transit search failed: %(error)s",
            )
            % {"error": str(exc)},
            origin=origin,
            destination=destination,
            source="Yahoo! Japan Transit",
        )


__all__ = ["TOOL_SPEC", "run_tool"]

"""bitchat_geo: GeoHash channel support for pybitchat Nostr transport.

GeoHash channels let users in the same geographic area communicate via Nostr
relays without needing BLE range. Wire-compatible with the official bitchat app.
"""

from __future__ import annotations

from typing import Any

# ---- GeoHash encoder (pure Python, no deps) --------------------------------

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
# (note: geohash uses a modified base32, skipping a,i,l,o)


def _geohash_encode(lat: float, lng: float, precision: int = 6) -> str:
    """Encode lat/lng to a geohash string.

    Args:
        lat: Latitude (-90 to 90)
        lng: Longitude (-180 to 180)
        precision: Number of characters (default 6 ≈ 1.2km accuracy)

    Returns:
        Geohash string.
    """
    lat_range = [-90.0, 90.0]
    lng_range = [-180.0, 180.0]
    result: list[str] = []
    is_lng = True
    bit = 0
    idx = 0

    while len(result) < precision:
        if is_lng:
            mid = (lng_range[0] + lng_range[1]) / 2
            if lng > mid:
                idx |= 1 << (4 - bit)
                lng_range[0] = mid
            else:
                lng_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid:
                idx |= 1 << (4 - bit)
                lat_range[0] = mid
            else:
                lat_range[1] = mid

        is_lng = not is_lng
        bit += 1

        if bit > 4:
            result.append(_BASE32[idx])
            bit = 0
            idx = 0

    return "".join(result)


def _geohash_decode(geohash: str) -> tuple[float, float, float, float]:
    """Decode a geohash to bounding box (lat_min, lat_max, lng_min, lng_max)."""
    lat_range = [-90.0, 90.0]
    lng_range = [-180.0, 180.0]
    is_lng = True

    for char in geohash:
        try:
            idx = _BASE32.index(char)
        except ValueError:
            continue
        for bit in range(4, -1, -1):
            if is_lng:
                mid = (lng_range[0] + lng_range[1]) / 2
                if idx & (1 << bit):
                    lng_range[0] = mid
                else:
                    lng_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if idx & (1 << bit):
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            is_lng = not is_lng

    return lat_range[0], lat_range[1], lng_range[0], lng_range[1]


# ---- Geo channel management -------------------------------------------------

# Active geo channel subscriptions: geohash -> set of NostrTransport instances
_GEO_CHANNELS: dict[str, set[Any]] = {}

# Approximate accuracy per geohash length
_GEO_PRECISION = {
    1: "~5000km",
    2: "~1250km",
    3: "~156km",
    4: "~39km",
    5: "~4.9km",
    6: "~1.2km",
    7: "~152m",
    8: "~38m",
    9: "~4.8m",
    10: "~0.6m",
}


def geo_peer_id(geohash: str) -> str:
    """Derive a Nostr peer ID for a geohash channel.

    Format: "nostr:" + geohash (matches upstream nostr_geo_chat_peer_id).
    """
    return _("geo.nostr_uri", default=f"nostr:{geohash}")


def join_geo_channel_by_hash(
    nostr_transport: Any,
    geohash: str,
) -> dict[str, Any]:
    """Join a geohash channel directly by geohash string.

    Args:
        nostr_transport: NostrTransport instance.
        geohash: Geohash string (e.g. "xn0m7d" or "mesh").

    Returns:
        Result dict with ok/geohash/precision/accuracy.
    """
    geohash = geohash.strip().lstrip("#")
    if not geohash:
        return {"ok": False, "error": "Empty geohash"}

    precision = len(geohash)
    accuracy = _GEO_PRECISION.get(precision, f"~{precision} chars")
    peer_id = geo_peer_id(geohash)

    # Track channel membership
    if geohash not in _GEO_CHANNELS:
        _GEO_CHANNELS[geohash] = set()
    _GEO_CHANNELS[geohash].add(id(nostr_transport))

    # Tell the transport to add subscription filter
    if hasattr(nostr_transport, "add_geo_filter"):
        nostr_transport.add_geo_filter(peer_id)

    return {
        "ok": True,
        "geohash": geohash,
        "peer_id": peer_id,
        "precision": precision,
        "accuracy": accuracy,
    }


def join_geo_channel(
    nostr_transport: Any,
    lat: float,
    lng: float,
    precision: int = 6,
) -> dict[str, Any]:
    """Join a geohash channel by coordinates."""
    if lat < -90 or lat > 90:
        return {"ok": False, "error": "Invalid latitude"}
    if lng < -180 or lng > 180:
        return {"ok": False, "error": "Invalid longitude"}

    geohash = _geohash_encode(lat, lng, precision)
    res = join_geo_channel_by_hash(nostr_transport, geohash)
    res["lat"] = lat
    res["lng"] = lng
    return res


def leave_geo_channel(
    nostr_transport: Any,
    geohash: str,
) -> dict[str, Any]:
    """Leave a geohash channel."""
    peer_id = geo_peer_id(geohash)
    if geohash in _GEO_CHANNELS:
        _GEO_CHANNELS[geohash].discard(id(nostr_transport))
        if not _GEO_CHANNELS[geohash]:
            del _GEO_CHANNELS[geohash]

    if hasattr(nostr_transport, "remove_geo_filter"):
        nostr_transport.remove_geo_filter(peer_id)

    return {"ok": True, "geohash": geohash, "peer_id": peer_id}


def list_geo_channels() -> dict[str, Any]:
    """List all active geo channel subscriptions."""
    channels = {}
    for geohash, instances in _GEO_CHANNELS.items():
        channels[geohash] = {
            "peer_id": geo_peer_id(geohash),
            "listeners": len(instances),
        }
    return {"ok": True, "channels": channels}

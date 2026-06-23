"""In-memory cache for Matter tools.

Provides transparent caching of tool results by (tool_name, args_key).
Useful for avoiding repeated JSON parsing and data normalization when
the same query is made multiple times within a short period.

Usage:
    from ._matter_cache import matter_cache_get, matter_cache_put, matter_cache_invalidate

    cache_key = f"{dev}:{ctrl}:{bridge}:{endpoint}"
    cached = matter_cache_get("matter_device_status", cache_key)
    if cached:
        return cached
    ...  # compute result
    matter_cache_put("matter_device_status", cache_key, result, ttl=60)
"""

from __future__ import annotations

import os
import time
from typing import Any

_DEFAULT_TTL = 60  # seconds

# Cache storage: { (tool_name, cache_key): (expires_at, result_dict) }
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

# Stats
_cache_hits = 0
_cache_misses = 0
_cache_puts = 0


def _ttl_from_env() -> int:
    """Get TTL from UAGENT_MATTER_CACHE_TTL env var, or default."""
    try:
        return max(0, int(os.getenv("UAGENT_MATTER_CACHE_TTL", str(_DEFAULT_TTL))))
    except (ValueError, TypeError):
        return _DEFAULT_TTL


def matter_cache_get(tool_name: str, cache_key: str) -> dict[str, Any] | None:
    """Return cached result for (tool_name, cache_key), or None."""
    if not cache_key:
        return None
    global _cache_hits, _cache_misses
    now = time.time()
    entry = _cache.get((tool_name, cache_key))
    if entry is not None:
        expires_at, result = entry
        if now < expires_at:
            _cache_hits += 1
            return result
        # Expired
        del _cache[(tool_name, cache_key)]
    _cache_misses += 1
    return None


def matter_cache_put(
    tool_name: str,
    cache_key: str,
    result: dict[str, Any],
    ttl: int | None = None,
) -> None:
    """Store result in cache with given TTL (or env default)."""
    if not cache_key:
        return
    global _cache_puts
    if ttl is None:
        ttl = _ttl_from_env()
    if ttl <= 0:
        return  # caching disabled
    expires_at = time.time() + ttl
    _cache[(tool_name, cache_key)] = (expires_at, result)
    _cache_puts += 1


def matter_cache_invalidate(tool_name: str | None = None, cache_key: str | None = None) -> int:
    """Invalidate cache entries.

    Args:
        tool_name: If set, only invalidate entries for this tool.
        cache_key: If set, only invalidate entries with this key (requires tool_name).

    Returns:
        Number of invalidated entries.
    """
    global _cache
    if tool_name is None:
        count = len(_cache)
        _cache.clear()
        return count

    if cache_key is not None:
        count = 1 if (tool_name, cache_key) in _cache else 0
        _cache.pop((tool_name, cache_key), None)
        return count

    # Invalidate all entries for a tool
    keys_to_delete = [k for k in _cache if k[0] == tool_name]
    for k in keys_to_delete:
        del _cache[k]
    return len(keys_to_delete)


def matter_cache_device_invalidate(device_id: str) -> int:
    """Invalidate all cache entries containing the given device_id in their key."""
    global _cache
    keys_to_delete = [
        k for k in _cache
        if device_id.casefold() in k[1].casefold()
    ]
    for k in keys_to_delete:
        del _cache[k]
    return len(keys_to_delete)


def matter_cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    now = time.time()
    active = sum(1 for v in _cache.values() if v[0] > now)
    expired = len(_cache) - active
    return {
        "cached_entries": active,
        "expired_entries": expired,
        "total_slots": len(_cache),
        "hits": _cache_hits,
        "misses": _cache_misses,
        "puts": _cache_puts,
        "hit_ratio": round(_cache_hits / max(1, _cache_hits + _cache_misses), 3),
        "ttl_seconds": _ttl_from_env(),
    }

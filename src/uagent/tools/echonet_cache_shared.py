from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

_CACHE_LOCK = threading.Lock()
_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_DEFAULT_TTL_SECONDS = 10
_DEFAULT_NAMESPACE_ORDER = ("scan", "node_status")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _normalize_namespace(namespace: str | None) -> str:
    raw = str(namespace or "").strip().lower()
    return raw or "default"


def _serialize_key(key: Any) -> str:
    if isinstance(key, str):
        return key
    try:
        return json.dumps(
            key, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except Exception:
        return repr(key)


def _entry_age_ms(entry: dict[str, Any]) -> int:
    try:
        created = float(entry.get("created_monotonic", 0.0))
    except Exception:
        created = 0.0
    return max(0, int((time.monotonic() - created) * 1000))


def cache_get(
    namespace: str, key: Any, ttl_seconds: int | None = None
) -> dict[str, Any] | None:
    ttl = _DEFAULT_TTL_SECONDS if ttl_seconds is None else max(0, int(ttl_seconds))
    cache_key = (_normalize_namespace(namespace), _serialize_key(key))
    with _CACHE_LOCK:
        entry = _CACHE.get(cache_key)
        if not entry:
            return None
        age_ms = _entry_age_ms(entry)
        if ttl and age_ms > ttl * 1000:
            _CACHE.pop(cache_key, None)
            return None
        return {
            "value": entry.get("value"),
            "created_at": entry.get("created_at"),
            "age_ms": age_ms,
            "namespace": cache_key[0],
            "key": cache_key[1],
        }


def cache_set(namespace: str, key: Any, value: Any) -> dict[str, Any]:
    cache_key = (_normalize_namespace(namespace), _serialize_key(key))
    entry = {
        "value": value,
        "created_at": _now_iso(),
        "created_monotonic": time.monotonic(),
    }
    with _CACHE_LOCK:
        _CACHE[cache_key] = entry
    return {
        "namespace": cache_key[0],
        "key": cache_key[1],
        "created_at": entry["created_at"],
    }


def cache_clear(namespace: str | None = None) -> int:
    target = _normalize_namespace(namespace) if namespace is not None else None
    removed = 0
    with _CACHE_LOCK:
        if target is None:
            removed = len(_CACHE)
            _CACHE.clear()
            return removed
        for cache_key in list(_CACHE.keys()):
            if cache_key[0] == target:
                _CACHE.pop(cache_key, None)
                removed += 1
    return removed


def cache_snapshot() -> dict[str, Any]:
    with _CACHE_LOCK:
        items = []
        counts: dict[str, int] = {}
        for (namespace, key), entry in sorted(_CACHE.items()):
            counts[namespace] = counts.get(namespace, 0) + 1
            items.append(
                {
                    "namespace": namespace,
                    "key": key,
                    "created_at": entry.get("created_at"),
                    "age_ms": _entry_age_ms(entry),
                }
            )
    return {
        "ok": True,
        "count": len(items),
        "namespaces": counts,
        "items": items,
        "generated_at": _now_iso(),
    }


def namespace_names() -> list[str]:
    with _CACHE_LOCK:
        return sorted({namespace for namespace, _ in _CACHE.keys()})


def default_namespace_order() -> tuple[str, ...]:
    return _DEFAULT_NAMESPACE_ORDER

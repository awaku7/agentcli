"""Event subscription manager for Matter devices.

Manages active subscriptions to device state changes.
Currently uses polling simulation since actual Matter events
depend on the transport layer (not implemented locally).
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

_MAX_SUBSCRIPTIONS = 10

_subscriptions: dict[str, dict[str, Any]] = {}


def _max_subs() -> int:
    try:
        return max(
            1,
            int(os.getenv("UAGENT_MATTER_MAX_SUBSCRIPTIONS", str(_MAX_SUBSCRIPTIONS))),
        )
    except (ValueError, TypeError):
        return _MAX_SUBSCRIPTIONS


def create_subscription(
    device_id: str,
    endpoint: str | None = None,
    cluster: str | None = None,
    attribute: str | None = None,
    min_interval: int = 0,
    max_interval: int = 300,
    duration: int = 3600,
) -> dict[str, Any]:
    """Create a new subscription.

    Returns:
        Subscription info dict with subscription_id.
    """
    # Check for duplicate
    for sub_id, sub in _subscriptions.items():
        if sub.get("dev") == device_id and not sub.get("expired", False):
            # Duplicate - update existing
            sub["endpoint"] = endpoint
            sub["cluster"] = cluster
            sub["attribute"] = attribute
            sub["min_interval"] = min_interval
            sub["max_interval"] = max_interval
            sub["duration"] = duration
            sub["expires_at"] = time.time() + duration
            sub["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            sub["expired"] = False
            return _format_sub(sub_id, sub)

    # Check max subscriptions
    active = count_active()
    if active >= _max_subs():
        # Auto-remove oldest expired
        oldest_active = min(
            (s for s in _subscriptions.values() if not s.get("expired", False)),
            key=lambda s: s.get("created_at", 0),
            default=None,
        )
        if oldest_active:
            oldest_active["expired"] = True

    sub_id = str(uuid.uuid4())[:8]
    now = time.time()
    _subscriptions[sub_id] = {
        "dev": device_id,
        "endpoint": endpoint,
        "cluster": cluster,
        "attribute": attribute,
        "min_interval": min_interval,
        "max_interval": max_interval,
        "duration": duration,
        "expires_at": now + duration,
        "created_at": now,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expired": False,
    }
    return _format_sub(sub_id, _subscriptions[sub_id])


def _format_sub(sub_id: str, sub: dict[str, Any]) -> dict[str, Any]:
    remaining = max(0, int(sub["expires_at"] - time.time()))
    return {
        "subscription_id": sub_id,
        "dev": sub["dev"],
        "endpoint": sub.get("endpoint"),
        "cluster": sub.get("cluster"),
        "attribute": sub.get("attribute"),
        "min_interval": sub.get("min_interval"),
        "max_interval": sub.get("max_interval"),
        "duration": sub.get("duration"),
        "remaining_seconds": remaining,
        "expired": sub.get("expired", False) or remaining <= 0,
        "created_at": datetime.fromtimestamp(
            sub.get("created_at", 0), tz=timezone.utc
        ).isoformat(timespec="seconds"),
    }


def remove_subscription(subscription_id: str) -> bool:
    """Remove a subscription by ID. Returns True if found."""
    if subscription_id in _subscriptions:
        _subscriptions[subscription_id]["expired"] = True
        return True
    return False


def list_subscriptions() -> list[dict[str, Any]]:
    """Return all active subscriptions."""
    now = time.time()
    results = []
    for sub_id, sub in _subscriptions.items():
        if sub.get("expired", False):
            continue
        if sub["expires_at"] <= now:
            sub["expired"] = True
            continue
        results.append(_format_sub(sub_id, sub))
    return results


def count_active() -> int:
    """Count active (non-expired) subscriptions."""
    return len(list_subscriptions())

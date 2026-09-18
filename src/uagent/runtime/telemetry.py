"""Small helpers for reconciling optional provider usage telemetry."""

from __future__ import annotations

from typing import Any, Mapping

_TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens")


def reconcile_usage(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> dict[str, int]:
    """Return non-negative token deltas when provider usage is available.

    Providers may omit usage on streaming or retry responses. Missing values
    are therefore omitted rather than treated as zero, so telemetry never
    claims a precise cost from incomplete data.
    """

    previous = before if isinstance(before, Mapping) else {}
    current = after if isinstance(after, Mapping) else {}
    result: dict[str, int] = {}
    for field in _TOKEN_FIELDS:
        raw_after = current.get(field)
        if not isinstance(raw_after, (int, float)) or isinstance(raw_after, bool):
            continue
        raw_before = previous.get(field)
        before_value = (
            int(raw_before)
            if isinstance(raw_before, (int, float)) and not isinstance(raw_before, bool)
            else 0
        )
        result[f"{field}_delta"] = max(0, int(raw_after) - before_value)
    return result


__all__ = ["reconcile_usage"]

"""Shared projection helpers for public round outcomes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_PUBLIC_OUTCOME_KEYS = (
    "round",
    "status",
    "reason",
    "tool_calls",
    "assistant_chars",
    "reasoning_chars",
    "duration_ms",
    "summary",
)


def _object_projection(value: Any) -> dict[str, Any]:
    """Project legacy/registry outcome objects without exposing raw payloads."""
    result: dict[str, Any] = {}
    for key in _PUBLIC_OUTCOME_KEYS:
        if hasattr(value, key):
            item = getattr(value, key)
            if key == "tool_calls":
                result[key] = len(item or ())
            elif key == "summary" and item is not None:
                serializer = getattr(item, "to_dict", None)
                result[key] = serializer() if callable(serializer) else dict(item)
            elif key != "summary":
                result[key] = item
    identifiers = getattr(value, "identifiers", None)
    if "round" not in result and identifiers is not None:
        round_id = getattr(identifiers, "round_id", None)
        if round_id is not None:
            result["round"] = round_id
    summary = result.get("summary")
    if isinstance(summary, Mapping):
        for key in (
            "status",
            "tool_call_count",
            "assistant_chars",
            "reasoning_chars",
            "duration_ms",
        ):
            if key in summary and key not in result:
                result[key] = summary[key]
        if "tool_call_count" in summary and "tool_calls" not in result:
            result["tool_calls"] = summary["tool_call_count"]
    return result


def project_round_outcome(value: Any) -> dict[str, Any]:
    """Return a detached, JSON-ready mapping for host-facing consumers."""
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if value is None:
        return {}
    return _object_projection(value)


def round_outcome_event(value: Any) -> dict[str, Any]:
    """Build the common Web/GUI event envelope for a round outcome."""
    outcome = project_round_outcome(value)
    if not outcome:
        return {}
    return {"type": "round_outcome", **outcome}


def round_outcome_key(value: Any) -> tuple[Any, Any, Any]:
    """Return the stable identity used to suppress duplicate host updates."""
    outcome = project_round_outcome(value)
    return (
        outcome.get("round"),
        outcome.get("status"),
        outcome.get("reason"),
    )


__all__ = [
    "project_round_outcome",
    "round_outcome_event",
    "round_outcome_key",
]

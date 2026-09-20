"""Shared projection helpers for public round outcomes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def project_round_outcome(value: Any) -> dict[str, Any]:
    """Return a detached, JSON-ready mapping for host-facing consumers."""
    if not isinstance(value, Mapping) or not value:
        return {}
    return {str(key): item for key, item in value.items()}


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

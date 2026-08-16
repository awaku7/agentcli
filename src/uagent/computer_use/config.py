"""Shared Computer Use policy construction for all entry points."""

from __future__ import annotations

import os

from .actions import SUPPORTED_ACTIONS
from .policy import ComputerUsePolicy


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return max(0.1, float(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _csv(name: str, *, default: frozenset[str] = frozenset()) -> frozenset[str]:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return frozenset(item.strip().lower() for item in value.split(",") if item.strip())


def computer_use_policy_from_env() -> ComputerUsePolicy:
    """Build the common policy used by CLI, GUI, Web, and A2A."""
    return ComputerUsePolicy(
        enabled=_bool("UAGENT_COMPUTER_USE", False),
        # Keep the shared policy's historical default. Runtime selection is
        # handled independently by the entrypoint runtime manager.
        environment="desktop",
        require_confirmation=_bool("UAGENT_COMPUTER_REQUIRE_CONFIRMATION", True),
        allowed_actions=_csv(
            "UAGENT_COMPUTER_ALLOWED_ACTIONS", default=SUPPORTED_ACTIONS
        ),
        allowed_domains=_csv("UAGENT_COMPUTER_ALLOWED_DOMAINS"),
        max_actions=_int("UAGENT_COMPUTER_MAX_ACTIONS", 50),
        max_turns=_int("UAGENT_COMPUTER_MAX_TURNS", 20),
        timeout=_float("UAGENT_COMPUTER_TIMEOUT", 300.0),
    )

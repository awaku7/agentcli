"""Shared Computer Use safety policy primitives."""

from __future__ import annotations

from dataclasses import dataclass

from .actions import ComputerAction


@dataclass(frozen=True)
class PolicyDecision:
    """Result of checking one action against a Computer Use policy."""

    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""


@dataclass(frozen=True)
class ComputerUsePolicy:
    """Common policy consumed by CLI, GUI, Web, and A2A entry points."""

    enabled: bool
    environment: str
    require_confirmation: bool
    allowed_actions: frozenset[str]
    allowed_domains: frozenset[str]
    max_actions: int
    max_turns: int
    timeout: float

    def check(
        self,
        action: ComputerAction,
        *,
        domain: str | None = None,
        environment: str | None = None,
    ) -> PolicyDecision:
        """Check whether an action may proceed before Runtime execution."""
        if not self.enabled:
            return PolicyDecision(False, reason="computer use is disabled")
        requested_environment = environment or self.environment
        if requested_environment != self.environment:
            return PolicyDecision(
                False,
                reason=f"environment is not allowed: {requested_environment}",
            )
        if action.action not in self.allowed_actions:
            return PolicyDecision(
                False,
                reason=f"action is not allowed: {action.action}",
            )
        # Domain allowlists apply to browser navigation only. Desktop actions
        # (mouse/keyboard/screenshot) have no URL domain and must not be
        # rejected merely because ``domain`` is None.
        if (
            requested_environment != "desktop"
            and self.allowed_domains
            and domain not in self.allowed_domains
        ):
            return PolicyDecision(False, reason=f"domain is not allowed: {domain}")
        if self.require_confirmation:
            return PolicyDecision(
                False,
                requires_confirmation=True,
                reason="user confirmation is required",
            )
        return PolicyDecision(True)

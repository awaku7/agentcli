"""Shared Computer Use safety policy primitives."""

from __future__ import annotations

from dataclasses import dataclass

from .actions import ComputerAction
from ..i18n import _


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
            return PolicyDecision(False, reason=_("computer use is disabled"))
        requested_environment = environment or self.environment
        if requested_environment != self.environment:
            return PolicyDecision(
                False,
                reason=_("environment is not allowed: %(environment)s")
                % {"environment": requested_environment},
            )
        if action.action not in self.allowed_actions:
            return PolicyDecision(
                False,
                reason=_("action is not allowed: %(action)s")
                % {"action": action.action},
            )
        # Domain allowlists apply to navigation targets and, when known, the
        # current browser origin. Desktop input actions have no URL domain and
        # remain usable when ``domain`` is None.
        if self.allowed_domains:
            normalized_domain = str(domain or "").strip().lower().rstrip(".")
            allowed_domains = {
                str(item).strip().lower().rstrip(".") for item in self.allowed_domains
            }
            if action.action == "navigate":
                domain_blocked = (
                    not normalized_domain or normalized_domain not in allowed_domains
                )
            else:
                domain_blocked = bool(normalized_domain) and (
                    normalized_domain not in allowed_domains
                )
            if domain_blocked:
                return PolicyDecision(
                    False,
                    reason=_("domain is not allowed: %(domain)s")
                    % {"domain": normalized_domain or "<unknown>"},
                )
        if self.require_confirmation:
            return PolicyDecision(
                False,
                requires_confirmation=True,
                reason=_("user confirmation is required"),
            )
        return PolicyDecision(True)

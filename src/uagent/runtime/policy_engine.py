"""Unified permission decisions built on the existing tool side-effect policy."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Any

from ..tools.enterprise_policy import EnterprisePolicy
from ..tools.tool_policy import SideEffect, policy_for


class Permission(IntEnum):
    NONE = 0
    READ_ONLY = 1
    PROPOSE_ONLY = 2
    WRITE = 3
    ADMIN = 4

    @classmethod
    def assert_child_allowed(
        cls, parent: "Permission", child: "Permission"
    ) -> None:
        if child > parent:
            raise ValueError(
                f"child permission {child.name} exceeds parent {parent.name}"
            )


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


class UnifiedPolicy:
    """Single public policy facade for runtime and enterprise rules."""

    def __init__(
        self,
        enterprise: EnterprisePolicy | None = None,
        permission: Permission | None = None,
    ) -> None:
        self.enterprise = enterprise or EnterprisePolicy()
        self.permission = permission

    @classmethod
    def from_file(
        cls, path: str, *, permission: Permission | None = None
    ) -> "UnifiedPolicy":
        return cls(EnterprisePolicy.from_file(path), permission)

    @classmethod
    def from_environment(cls) -> "UnifiedPolicy":
        return cls(EnterprisePolicy.from_environment(), permission_from_environment())

    def decide(
        self, tool_name: str, args: dict[str, Any] | None = None
    ) -> PolicyDecision:
        args = args or {}
        enterprise = self.enterprise.decide(tool_name, args)
        if enterprise.denied:
            return PolicyDecision.DENY
        if self.permission is None:
            return (
                PolicyDecision.CONFIRM
                if enterprise.requires_confirmation
                else PolicyDecision.ALLOW
            )
        runtime = evaluate_tool(tool_name, args, self.permission)
        if runtime is PolicyDecision.DENY or enterprise.requires_confirmation:
            return PolicyDecision.DENY if runtime is PolicyDecision.DENY else PolicyDecision.CONFIRM
        return runtime


def permission_from_environment() -> Permission | None:
    """Return the optional process-wide policy level.

    Unset means legacy behavior. Invalid values fail closed to read-only.
    """
    import os

    raw = os.environ.get("UAGENT_POLICY_LEVEL")
    if raw is None or not raw.strip():
        return None
    try:
        return Permission[raw.strip().upper()]
    except KeyError:
        return Permission.READ_ONLY


def evaluate_tool(
    tool_name: str,
    args: dict[str, Any] | None,
    permission: Permission,
) -> PolicyDecision:
    """Return a conservative decision without prompting the user."""
    if permission <= Permission.NONE:
        return PolicyDecision.DENY

    policy = policy_for(tool_name, args)
    if policy.side_effect is SideEffect.READ_ONLY:
        return PolicyDecision.ALLOW
    if permission <= Permission.READ_ONLY:
        return PolicyDecision.DENY
    if permission == Permission.PROPOSE_ONLY:
        return PolicyDecision.CONFIRM
    if policy.side_effect in {SideEffect.EXTERNAL_SEND, SideEffect.DESTRUCTIVE}:
        return PolicyDecision.CONFIRM
    if policy.requires_confirmation:
        return PolicyDecision.CONFIRM
    return PolicyDecision.ALLOW


__all__ = [
    "Permission",
    "PolicyDecision",
    "evaluate_tool",
    "permission_from_environment",
]

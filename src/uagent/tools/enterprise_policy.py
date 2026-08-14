"""Organization-level policy controls layered on top of ToolPolicy."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PolicyDecision:
    action: str = "allow"
    reason: str = ""

    @property
    def denied(self) -> bool:
        return self.action == "deny"

    @property
    def requires_confirmation(self) -> bool:
        return self.action == "confirm"


@dataclass
class EnterprisePolicy:
    """Configurable policy for tools, providers, MCP, and network resources."""

    tools: dict[str, str] = field(default_factory=dict)
    providers: dict[str, str] = field(default_factory=dict)
    mcp_servers: dict[str, str] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    credentials: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "EnterprisePolicy":
        raw = raw or {}
        return cls(
            tools=_actions(raw.get("tools")),
            providers=_actions(raw.get("providers")),
            mcp_servers=_actions(raw.get("mcp_servers")),
            network=dict(raw.get("network") or {}),
            credentials=_actions(raw.get("credentials")),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "EnterprisePolicy":
        source = Path(path).expanduser()
        text = source.read_text(encoding="utf-8")
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                raise ValueError("YAML policy requires PyYAML; use JSON instead") from exc
            raw = yaml.safe_load(text) or {}
        if not isinstance(raw, Mapping):
            raise ValueError("enterprise policy must be an object")
        return cls.from_mapping(raw)

    @classmethod
    def from_environment(cls) -> "EnterprisePolicy":
        path = (os.environ.get("UAGENT_POLICY_FILE") or "").strip()
        return cls.from_file(path) if path else cls()

    def decide(self, tool_name: str, args: Mapping[str, Any] | None = None) -> PolicyDecision:
        args = args or {}
        action = _normalize_action(self.tools.get(tool_name, "allow"))
        if action != "allow":
            return PolicyDecision(action, f"tool:{tool_name}")

        provider = str(args.get("provider") or "").strip().lower()
        if provider and provider in self.providers:
            action = _normalize_action(self.providers[provider])
            if action != "allow":
                return PolicyDecision(action, f"provider:{provider}")

        url = str(args.get("url") or args.get("host") or "").strip()
        if url:
            default = _normalize_action(self.network.get("default", "allow"))
            allowed = self.network.get("allowlist") or self.network.get("allow") or []
            if default == "deny" and not any(str(item) in url for item in allowed):
                return PolicyDecision("deny", f"network:{url}")

        return PolicyDecision("allow")


def _actions(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(item, Mapping):
            item = item.get("action", "allow")
        result[str(key)] = _normalize_action(item)
    return result


def _normalize_action(value: Any) -> str:
    action = str(value or "allow").strip().lower()
    if action not in {"allow", "deny", "confirm"}:
        raise ValueError(f"unsupported policy action: {action}")
    return action


_DEFAULT_POLICY = EnterprisePolicy.from_environment()


def get_enterprise_policy() -> EnterprisePolicy:
    return _DEFAULT_POLICY


def set_enterprise_policy(policy: EnterprisePolicy) -> None:
    global _DEFAULT_POLICY
    _DEFAULT_POLICY = policy


__all__ = ["EnterprisePolicy", "PolicyDecision", "get_enterprise_policy", "set_enterprise_policy"]

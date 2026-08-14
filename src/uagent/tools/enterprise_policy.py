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
    skills: dict[str, str] = field(default_factory=dict)
    plugins: dict[str, str] = field(default_factory=dict)
    roles: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "EnterprisePolicy":
        raw = raw or {}
        return cls(
            tools=_actions(raw.get("tools")),
            providers=_actions(raw.get("providers")),
            mcp_servers=_actions(raw.get("mcp_servers")),
            network=dict(raw.get("network") or {}),
            credentials=_actions(raw.get("credentials")),
            skills=_actions(raw.get("skills")),
            plugins=_actions(raw.get("plugins")),
            roles={str(role): _actions(value.get("tools")) for role, value in (raw.get("roles") or {}).items() if isinstance(value, Mapping)},
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

    def decide_credential(self, name: str) -> PolicyDecision:
        action = _normalize_action(self.credentials.get(name, "allow"))
        return PolicyDecision(action, f"credential:{name}") if action != "allow" else PolicyDecision("allow")

    def decide_mcp_server(self, url: str) -> PolicyDecision:
        for pattern, action in self.mcp_servers.items():
            if pattern in url:
                normalized = _normalize_action(action)
                return PolicyDecision(normalized, f"mcp:{pattern}")
        return PolicyDecision("allow")

    def decide_skill(self, name: str) -> PolicyDecision:
        action = _normalize_action(self.skills.get(name, "allow"))
        return PolicyDecision(action, f"skill:{name}") if action != "allow" else PolicyDecision("allow")

    def decide_plugin(self, name: str) -> PolicyDecision:
        action = _normalize_action(self.plugins.get(name, "allow"))
        return PolicyDecision(action, f"plugin:{name}") if action != "allow" else PolicyDecision("allow")

    def decide(self, tool_name: str, args: Mapping[str, Any] | None = None) -> PolicyDecision:
        args = args or {}
        role = str(args.get("role") or os.environ.get("UAGENT_ROLE") or "").strip()
        role_actions = self.roles.get(role, {})
        action = _normalize_action(role_actions.get(tool_name, self.tools.get(tool_name, "allow")))
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
_POLICY_PATH = (os.environ.get("UAGENT_POLICY_FILE") or "").strip()
_POLICY_MTIME: float | None = None
if _POLICY_PATH:
    try:
        _POLICY_MTIME = Path(_POLICY_PATH).stat().st_mtime
    except OSError:
        pass


def get_enterprise_policy() -> EnterprisePolicy:
    global _DEFAULT_POLICY, _POLICY_MTIME
    if _POLICY_PATH:
        try:
            mtime = Path(_POLICY_PATH).stat().st_mtime
            if _POLICY_MTIME != mtime:
                _DEFAULT_POLICY = EnterprisePolicy.from_file(_POLICY_PATH)
                _POLICY_MTIME = mtime
        except OSError:
            pass
    return _DEFAULT_POLICY


def set_enterprise_policy(policy: EnterprisePolicy) -> None:
    global _DEFAULT_POLICY
    _DEFAULT_POLICY = policy


__all__ = ["EnterprisePolicy", "PolicyDecision", "get_enterprise_policy", "set_enterprise_policy"]

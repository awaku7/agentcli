"""Organization-level policy controls layered on top of ToolPolicy."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import SplitResult, urlsplit

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


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
    mcp_tools: dict[str, str] = field(default_factory=dict)
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
            mcp_tools=_actions(raw.get("mcp_tools")),
            network=dict(raw.get("network") or {}),
            credentials=_actions(raw.get("credentials")),
            skills=_actions(raw.get("skills")),
            plugins=_actions(raw.get("plugins")),
            roles={
                str(role): _actions(value.get("tools"))
                for role, value in (raw.get("roles") or {}).items()
                if isinstance(value, Mapping)
            },
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
                raise ValueError(
                    _(
                        "err.yaml_dependency",
                        default="YAML policy requires PyYAML; use JSON instead",
                    )
                ) from exc
            raw = yaml.safe_load(text) or {}
        if not isinstance(raw, Mapping):
            raise ValueError(
                _(
                    "err.policy_object_required",
                    default="enterprise policy must be an object",
                )
            )
        return cls.from_mapping(raw)

    @classmethod
    def from_environment(cls) -> "EnterprisePolicy":
        """Load the configured policy, creating an allow-all default if absent."""
        path = (os.environ.get("UAGENT_POLICY_FILE") or "").strip()
        if not path:
            from ..utils.paths import get_state_dir

            path = str(get_state_dir() / "enterprise-policy.yaml")
        target = Path(path).expanduser()
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            # JSON is valid YAML and keeps the generated default dependency-free.
            target.write_text(
                "{}\n",
                encoding="utf-8",
                newline="\n",
            )
            return cls()
        return cls.from_file(target)

    def decide_credential(self, name: str) -> PolicyDecision:
        action = _normalize_action(self.credentials.get(name, "allow"))
        return (
            PolicyDecision(action, f"credential:{name}")
            if action != "allow"
            else PolicyDecision("allow")
        )

    def decide_mcp_server(self, url: str) -> PolicyDecision:
        has_allowlist = False
        for pattern, action in self.mcp_servers.items():
            normalized = _normalize_action(action)
            has_allowlist = has_allowlist or normalized == "allow"
            if _endpoint_matches(str(pattern), url):
                return PolicyDecision(normalized, f"mcp:{pattern}")
        if has_allowlist:
            return PolicyDecision("deny", f"mcp:allowlist:{url}")
        return PolicyDecision("allow")

    def decide_skill(self, name: str) -> PolicyDecision:
        action = _normalize_action(self.skills.get(name, "allow"))
        return (
            PolicyDecision(action, f"skill:{name}")
            if action != "allow"
            else PolicyDecision("allow")
        )

    def decide_plugin(self, name: str) -> PolicyDecision:
        action = _normalize_action(self.plugins.get(name, "allow"))
        return (
            PolicyDecision(action, f"plugin:{name}")
            if action != "allow"
            else PolicyDecision("allow")
        )

    def decide(
        self, tool_name: str, args: Mapping[str, Any] | None = None
    ) -> PolicyDecision:
        args = args or {}
        role = str(args.get("role") or os.environ.get("UAGENT_ROLE") or "").strip()
        role_actions = self.roles.get(role, {})
        action = _normalize_action(
            role_actions.get(tool_name, self.tools.get(tool_name, "allow"))
        )
        if action != "allow":
            return PolicyDecision(action, f"tool:{tool_name}")

        # MCP tool-level gate: handle_mcp_v2 dispatches to a specific function
        # of a specific server, so the policy key is "server_name:tool_name"
        # (e.g. physical_vision:arm_sort). Unlisted MCP functions stay allow.
        if tool_name == "handle_mcp_v2":
            server = str(args.get("server_name") or "").strip()
            mcp_tool = str(args.get("tool_name") or "").strip()
            if server and mcp_tool:
                mcp_key = f"{server}:{mcp_tool}"
                mcp_action = _normalize_action(self.mcp_tools.get(mcp_key, "allow"))
                if mcp_action != "allow":
                    return PolicyDecision(mcp_action, f"mcp_tool:{mcp_key}")

        provider = str(args.get("provider") or "").strip().lower()
        if provider and provider in self.providers:
            action = _normalize_action(self.providers[provider])
            if action != "allow":
                return PolicyDecision(action, f"provider:{provider}")

        url = str(args.get("url") or args.get("host") or "").strip()
        if url:
            default = _normalize_action(self.network.get("default", "allow"))
            allowed = self.network.get("allowlist") or self.network.get("allow") or []
            if default == "deny" and not any(
                _endpoint_matches(str(item), url) for item in allowed
            ):
                return PolicyDecision("deny", f"network:{url}")

        return PolicyDecision("allow")


def _split_endpoint(value: str) -> SplitResult | None:
    raw = str(value or "").strip()
    if not raw or any(char.isspace() for char in raw):
        return None
    candidate = raw if "://" in raw else f"//{raw}"
    try:
        parsed = urlsplit(candidate)
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        _ = parsed.port
        return parsed
    except ValueError:
        return None


def _effective_port(parsed: SplitResult) -> int | None:
    if parsed.port is not None:
        return parsed.port
    return {"http": 80, "https": 443}.get(parsed.scheme.lower())


def _host_matches(pattern_host: str, target_host: str) -> bool:
    pattern = pattern_host.rstrip(".").lower()
    target = target_host.rstrip(".").lower()
    return bool(
        pattern and target and (target == pattern or target.endswith("." + pattern))
    )


def _path_matches(pattern_path: str, target_path: str) -> bool:
    pattern = pattern_path.rstrip("/") or "/"
    target = target_path or "/"
    return pattern == "/" or target == pattern or target.startswith(pattern + "/")


def _endpoint_matches(pattern: str, target: str) -> bool:
    """Match endpoint policies by scheme/host/port/path boundaries."""
    expected = _split_endpoint(pattern)
    actual = _split_endpoint(target)
    if expected is None or actual is None:
        return False
    if expected.scheme and expected.scheme.lower() != actual.scheme.lower():
        return False
    if not _host_matches(expected.hostname or "", actual.hostname or ""):
        return False
    expected_port = _effective_port(expected)
    actual_port = _effective_port(actual)
    if expected_port is not None and expected_port != actual_port:
        return False
    if (
        not expected.scheme
        and expected.port is None
        and actual.scheme.lower() in {"http", "https"}
        and actual_port not in {80, 443}
    ):
        return False
    if (
        expected.path
        and expected.path != "/"
        and not _path_matches(expected.path, actual.path)
    ):
        return False
    return True


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
        raise ValueError(
            _(
                "err.unsupported_policy_action",
                default="unsupported policy action: {action}",
            ).format(action=action)
        )
    return action


_DEFAULT_POLICY = EnterprisePolicy.from_environment()
_POLICY_PATH = (os.environ.get("UAGENT_POLICY_FILE") or "").strip()
if not _POLICY_PATH:
    try:
        from ..utils.paths import get_state_dir

        _POLICY_PATH = str(get_state_dir() / "enterprise-policy.yaml")
    except Exception:
        _POLICY_PATH = ""
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


__all__ = [
    "EnterprisePolicy",
    "PolicyDecision",
    "get_enterprise_policy",
    "set_enterprise_policy",
]

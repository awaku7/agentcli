"""Fail-closed execution routing primitives for tools.

Remote Web and A2A can use the configured MXC ProcessContainer baseline. The
broker never falls back to a Host runner when isolation is required; higher
minimum isolation tiers remain fail-closed until an accepted backend exists.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum, IntEnum
import os
from typing import Any, Callable, Protocol


class ExecutionClass(str, Enum):
    SANDBOX = "sandbox"
    BROKERED = "brokered"
    DENY = "deny"
    LOCAL_HOST_PURE = "local_host_pure"


class SecurityProfile(str, Enum):
    LOCAL_TRUSTED = "local_trusted"
    REMOTE = "remote"


class IsolationLevel(IntEnum):
    NONE = 0
    PROCESS = 1
    CONTAINER = 2
    VM = 3


class SandboxCapability(str, Enum):
    SUBPROCESS_CONFINEMENT = "subprocess_confinement"
    FILESYSTEM_POLICY = "filesystem_policy"
    NETWORK_POLICY = "network_policy"
    RESOURCE_LIMITS = "resource_limits"


@dataclass(frozen=True)
class SandboxCapabilities:
    """Observed backend capabilities; declarations alone are not proof.

    ``remote_acceptance_passed`` is deliberately separate from the advertised
    isolation level and feature set. Remote routing must not be enabled by a
    backend probe, mock, or dry-run alone; a backend may set this only after
    the required host-specific isolation and limit-violation acceptance tests
    have passed.
    """

    isolation_level: IsolationLevel = IsolationLevel.NONE
    available: frozenset[SandboxCapability] = field(default_factory=frozenset)
    remote_acceptance_passed: bool = False

    def __post_init__(self) -> None:
        if type(self.remote_acceptance_passed) is not bool:
            raise ValueError("remote acceptance status must be a boolean")

    def satisfies(
        self,
        *,
        minimum_isolation: IsolationLevel,
        required: frozenset[SandboxCapability],
    ) -> bool:
        if not isinstance(self.isolation_level, IsolationLevel):
            return False
        try:
            available = frozenset(self.available)
        except Exception:
            return False
        if any(not isinstance(item, SandboxCapability) for item in available):
            return False
        return self.isolation_level >= minimum_isolation and required.issubset(
            available
        )


@dataclass(frozen=True)
class CancellationResult:
    execution_stopped: bool
    lease_terminated: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.execution_stopped) is not bool
            or type(self.lease_terminated) is not bool
        ):
            raise ValueError("cancellation result fields must be booleans")

    @property
    def safe_to_reuse(self) -> bool:
        return self.execution_stopped and not self.lease_terminated


class SandboxBackend(Protocol):
    """Backend contract kept independent of any OS SDK or implementation."""

    def probe(self, *, timeout_seconds: float) -> SandboxCapabilities: ...

    def create(self, spec: Any) -> Any: ...

    def start_execution(self, lease_handle: Any, request: Any) -> Any: ...

    def wait_execution(
        self, execution_handle: Any, *, timeout_seconds: float
    ) -> Any: ...

    def cancel_execution(
        self, execution_handle: Any, *, reason: str
    ) -> CancellationResult: ...

    def terminate(self, lease_handle: Any) -> None: ...

    def health(self, lease_handle: Any) -> bool: ...


def cancel_execution_safely(
    backend: SandboxBackend,
    execution_handle: Any,
    lease_handle: Any,
    *,
    reason: str,
) -> CancellationResult:
    """Keep a Lease only when the Backend confirms the specific execution stopped."""
    try:
        result = backend.cancel_execution(execution_handle, reason=reason)
        if not isinstance(result, CancellationResult):
            result = CancellationResult(execution_stopped=False)
    except Exception:
        result = CancellationResult(execution_stopped=False)
    if result.execution_stopped or result.lease_terminated:
        return result
    try:
        backend.terminate(lease_handle)
    except Exception:
        return CancellationResult(execution_stopped=False)
    return CancellationResult(execution_stopped=False, lease_terminated=True)


@dataclass(frozen=True)
class TrustedSandboxScope:
    """Trusted server-created execution scope; never construct from tool args."""

    deployment_id: str
    principal_id: str
    project_id: str
    scope_kind: str
    scope_id: str
    binding_generation: str = ""

    def __post_init__(self) -> None:
        required = (
            self.deployment_id,
            self.principal_id,
            self.project_id,
            self.scope_id,
        )
        if any(not str(value or "").strip() for value in required):
            raise ValueError("sandbox scope identifiers must be non-empty")
        if self.scope_kind not in {
            "cli-session",
            "gui-session",
            "web-room",
            "a2a-task",
        }:
            raise ValueError("unsupported sandbox scope kind")


def trusted_web_scope(turn_context: Any, room_id: str) -> TrustedSandboxScope | None:
    """Build a Web scope only from an authenticated, server-created TurnContext."""
    if (
        turn_context is None
        or getattr(turn_context, "entry_point", "") != "web"
        or getattr(turn_context, "room_id", "") != str(room_id or "")
        or not bool(getattr(turn_context, "authenticated", False))
        or str(getattr(turn_context, "authn_kind", "local")).strip().lower() == "local"
    ):
        return None
    try:
        return TrustedSandboxScope(
            deployment_id="web",
            principal_id=turn_context.principal_id,
            project_id=turn_context.project_id,
            scope_kind="web-room",
            scope_id=turn_context.room_id,
        )
    except (AttributeError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class RoutingDecision:
    execution_class: ExecutionClass
    allowed: bool
    reason: str = ""


_profile: ContextVar[SecurityProfile] = ContextVar(
    "uagent_execution_profile", default=SecurityProfile.LOCAL_TRUSTED
)


def current_profile() -> SecurityProfile:
    return _profile.get()


_sandbox_enabled: ContextVar[bool] = ContextVar("uagent_sandbox_enabled", default=False)
_scope: ContextVar[TrustedSandboxScope | None] = ContextVar(
    "uagent_sandbox_scope", default=None
)
_authorization_check: ContextVar[Callable[[], bool] | None] = ContextVar(
    "uagent_execution_authorization_check", default=None
)
_UNSET_AUTHORIZATION_CHECK = object()


def current_scope() -> TrustedSandboxScope | None:
    return _scope.get()


def current_authorization_valid(*, require_check: bool = False) -> bool:
    """Revalidate trusted ingress authorization at the execution boundary."""
    check = _authorization_check.get()
    if check is None:
        return not require_check
    try:
        return check() is True
    except Exception:
        return False


def computer_use_allowed() -> bool:
    """Computer Use is local-host-only and unavailable whenever Sandbox is on."""
    return (
        _profile.get() is SecurityProfile.LOCAL_TRUSTED and not _sandbox_enabled.get()
    )


def is_computer_use_tool_name(name: str) -> bool:
    return str(name or "").strip().lower() in {
        "computer",
        "computer_use",
        "computer_use_preview",
    }


def is_computer_use_tool_spec(spec: Any) -> bool:
    """Recognize function and provider-native Computer Use declarations."""
    if not isinstance(spec, dict):
        return False
    if (
        str(spec.get("type") or "").strip().lower()
        in {
            "computer",
            "computer_use",
            "computer_use_preview",
            "computer_toolset_20260801",
        }
        or "computer_use" in spec
    ):
        return True
    function = spec.get("function")
    if isinstance(function, dict) and is_computer_use_tool_name(function.get("name")):
        return True
    return False


@contextmanager
def execution_profile(
    profile: SecurityProfile,
    *,
    sandbox_enabled: bool = False,
    scope: TrustedSandboxScope | None = None,
    authorization_check: (
        Callable[[], bool] | None | object
    ) = _UNSET_AUTHORIZATION_CHECK,
):
    """Bind trusted ingress security settings for the current dispatch context.

    Nested dispatch scopes inherit the parent authorization callback unless a
    trusted caller explicitly supplies a replacement.
    """
    profile_token = _profile.set(profile)
    sandbox_token = _sandbox_enabled.set(bool(sandbox_enabled))
    scope_token = _scope.set(scope)
    if authorization_check is _UNSET_AUTHORIZATION_CHECK:
        authorization_token = _authorization_check.set(_authorization_check.get())
    else:
        authorization_token = _authorization_check.set(authorization_check)
    try:
        yield
    finally:
        _authorization_check.reset(authorization_token)
        _scope.reset(scope_token)
        _sandbox_enabled.reset(sandbox_token)
        _profile.reset(profile_token)


def current_sandbox_enabled() -> bool:
    return _sandbox_enabled.get()


def is_trusted_local_web(bind_host: str, identity_mode: str) -> bool:
    """Allow legacy Host routing only for the exact local-only startup pair."""
    return bind_host == "127.0.0.1" and identity_mode == "local"


def required_sandbox_capabilities(
    profile: SecurityProfile,
) -> tuple[IsolationLevel, frozenset[SandboxCapability]]:
    """Return the minimum isolation boundary selected for an execution profile.

    Standard Remote execution uses process/container isolation. Deployments that
    need VM isolation can set UAGENT_REMOTE_SANDBOX_MIN_ISOLATION=vm; until a
    VM backend with acceptance evidence is available, that setting fails closed.
    """
    required = frozenset(SandboxCapability)
    if profile is SecurityProfile.REMOTE:
        configured = (
            os.environ.get("UAGENT_REMOTE_SANDBOX_MIN_ISOLATION", "container")
            .strip()
            .lower()
        )
        minimum = (
            IsolationLevel.CONTAINER if configured == "container" else IsolationLevel.VM
        )
    else:
        minimum = IsolationLevel.PROCESS
    return minimum, required


# Explicit, no-argument control-plane services only. Their remote behavior is
# implemented here rather than by calling the regular Host tool runner.
_REMOTE_BROKERED = frozenset({"get_current_time"})


def classify_tool(tool_name: str, args: dict[str, Any] | None = None) -> ExecutionClass:
    name = str(tool_name or "").strip()
    if not name:
        return ExecutionClass.DENY
    if name in _REMOTE_BROKERED:
        if args:
            return ExecutionClass.DENY
        return ExecutionClass.BROKERED
    # Unknown, lazy-loaded, and ordinary registered tools are all isolated.
    return ExecutionClass.SANDBOX


def run_brokered_tool(tool_name: str) -> str:
    """Run one fixed broker operation without entering a generic tool runner."""
    if tool_name != "get_current_time":
        raise ValueError("unsupported broker operation")
    from datetime import datetime, timezone

    local_now = datetime.now().astimezone()
    utc_now = datetime.now(timezone.utc)
    lines = [
        "[get_current_time]",
        f"ISO8601 (Local): {local_now.isoformat()}",
        f"ISO8601 (UTC):   {utc_now.isoformat()}",
        f"Weekday:         {local_now.strftime('%A')}",
        f"Timezone Name:   {local_now.tzname()}",
        f"UTC Offset:      {local_now.strftime('%z')}",
        f"Year:            {local_now.year}",
        f"Month:           {local_now.month}",
        f"Day:             {local_now.day}",
        f"Hour:            {local_now.hour}",
        f"Minute:          {local_now.minute}",
        f"Second:          {local_now.second}",
        "NTP Sync:        N/A",
    ]
    return "\n".join(lines)


def route_tool(
    tool_name: str,
    args: dict[str, Any] | None = None,
    *,
    profile: SecurityProfile = SecurityProfile.LOCAL_TRUSTED,
    sandbox_enabled: bool = False,
    backend_available: bool = False,
    backend_capabilities: SandboxCapabilities | None = None,
    known_tool: bool = False,
) -> RoutingDecision:
    """Select a route without treating missing capabilities as permission."""
    execution_class = classify_tool(tool_name, args)
    if execution_class is ExecutionClass.DENY:
        return RoutingDecision(execution_class, False, "unknown or invalid tool")
    if (
        profile is SecurityProfile.REMOTE
        and execution_class is not ExecutionClass.BROKERED
        and not known_tool
    ):
        return RoutingDecision(
            ExecutionClass.DENY, False, "unknown or unregistered remote tool"
        )
    if profile is SecurityProfile.REMOTE and current_scope() is None:
        return RoutingDecision(
            execution_class, False, "trusted remote scope is required"
        )
    if execution_class is ExecutionClass.BROKERED and profile is SecurityProfile.REMOTE:
        return RoutingDecision(execution_class, True)
    if profile is SecurityProfile.LOCAL_TRUSTED and not sandbox_enabled:
        return RoutingDecision(execution_class, True)
    if profile is SecurityProfile.REMOTE and not sandbox_enabled:
        return RoutingDecision(execution_class, False, "remote sandbox is disabled")
    if not backend_available or backend_capabilities is None:
        return RoutingDecision(execution_class, False, "no compliant sandbox backend")
    minimum, required = required_sandbox_capabilities(profile)
    if not backend_capabilities.satisfies(minimum_isolation=minimum, required=required):
        return RoutingDecision(
            execution_class, False, "sandbox capabilities are insufficient"
        )
    if (
        profile is SecurityProfile.REMOTE
        and minimum >= IsolationLevel.VM
        and not backend_capabilities.remote_acceptance_passed
    ):
        return RoutingDecision(
            execution_class,
            False,
            "remote VM sandbox acceptance evidence is missing",
        )
    # The default Remote tier accepts verified ProcessContainer capabilities.
    # VM/high-assurance selection additionally requires host-specific acceptance
    # evidence and fails closed when that evidence is absent.
    return RoutingDecision(execution_class, True)
